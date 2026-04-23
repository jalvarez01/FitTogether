import logging
from dataclasses import dataclass
from itertools import islice
from typing import Iterable, Iterator, List, Optional

from django.db import connection
from django.db import transaction

from posts.models import Post
from posts.services.openai_moderation import PENDING, moderate_post

logger = logging.getLogger(__name__)


@dataclass
class ModerationRunStats:
    scanned: int = 0
    changed: int = 0
    unchanged: int = 0
    still_pending: int = 0
    failures: int = 0


def _iter_post_ids_from_table(
    *, include_all_statuses: bool, limit: Optional[int]
) -> Iterator[int]:
    query = "SELECT id FROM posts_post"
    params: List[object] = []

    if not include_all_statuses:
        query += " WHERE moderation_status = %s"
        params.append(Post.MODERATION_PENDING)

    query += " ORDER BY id ASC"

    if limit is not None and limit > 0:
        query += " LIMIT %s"
        params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        while True:
            rows = cursor.fetchmany(size=200)
            if not rows:
                break
            for row in rows:
                yield row[0]


def _chunked(iterable: Iterable[int], size: int) -> Iterator[List[int]]:
    iterator = iter(iterable)
    while True:
        chunk = list(islice(iterator, max(1, size)))
        if not chunk:
            break
        yield chunk


def reprocess_posts(
    *,
    include_all_statuses: bool = False,
    batch_size: int = 100,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> ModerationRunStats:
    """
    Reprocess moderation asynchronously-friendly from a command/worker context.

    - Default mode scans only pending posts.
    - include_all_statuses=True scans every post and reapplies current rules.
    - Idempotent: unchanged statuses are not written again.
    """

    stats = ModerationRunStats()
    post_ids = _iter_post_ids_from_table(
        include_all_statuses=include_all_statuses,
        limit=limit,
    )

    for id_batch in _chunked(post_ids, batch_size):
        posts_by_id = {
            post.id: post
            for post in Post.objects.select_related("author")
            .filter(id__in=id_batch)
            .order_by("id")
        }

        for post_id in id_batch:
            post = posts_by_id.get(post_id)
            if not post:
                # Post may have been deleted between reading ids and processing.
                continue

            stats.scanned += 1

            try:
                status, reason = moderate_post(post.content, post.image)
            except Exception:
                stats.failures += 1
                logger.exception("Unhandled moderation error for post_id=%s", post.id)
                continue

            if status == PENDING:
                stats.still_pending += 1
                logger.warning(
                    "Post moderation deferred again (post_id=%s, current_status=%s, reason=%s)",
                    post.id,
                    post.moderation_status,
                    reason,
                )
                continue

            if post.moderation_status == status:
                stats.unchanged += 1
                logger.info(
                    "Post moderation unchanged (post_id=%s, status=%s)",
                    post.id,
                    status,
                )
                continue

            logger.info(
                "Post moderation status update (post_id=%s, old_status=%s, new_status=%s, reason=%s)",
                post.id,
                post.moderation_status,
                status,
                reason,
            )

            if dry_run:
                stats.changed += 1
                continue

            with transaction.atomic():
                post.moderation_status = status
                post.save(update_fields=["moderation_status"])
            stats.changed += 1

    return stats
