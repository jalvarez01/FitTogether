from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Post
from .services.openai_moderation import PENDING, moderate_post
from users.models import WeekCompletion, WorkoutCompletion


class DeletePostTests(TestCase):
	def setUp(self):
		self.author = User.objects.create_user(username="author", password="testpass123")
		self.other_user = User.objects.create_user(username="other", password="testpass123")

	def test_author_can_delete_post_within_24_hours(self):
		post = Post.objects.create(author=self.author, content="My post")

		self.client.force_login(self.author)
		response = self.client.post(reverse("posts:delete_post", args=[post.id]))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("social:feed"))
		self.assertFalse(Post.objects.filter(id=post.id).exists())

	def test_author_cannot_delete_post_after_24_hours(self):
		post = Post.objects.create(author=self.author, content="Old post")
		Post.objects.filter(id=post.id).update(created_at=timezone.now() - timedelta(hours=25))

		self.client.force_login(self.author)
		response = self.client.post(reverse("posts:delete_post", args=[post.id]))

		self.assertEqual(response.status_code, 403)
		self.assertTrue(Post.objects.filter(id=post.id).exists())

	def test_non_author_cannot_delete_post(self):
		post = Post.objects.create(author=self.author, content="Protected post")

		self.client.force_login(self.other_user)
		response = self.client.post(reverse("posts:delete_post", args=[post.id]))

		self.assertEqual(response.status_code, 403)
		self.assertTrue(Post.objects.filter(id=post.id).exists())


class StreakConsistencyTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="streak_user", password="testpass123")
		self.user.profile.weekly_training_days = 1
		self.user.profile.save(update_fields=["weekly_training_days"])

	def test_only_approved_posts_create_completion(self):
		Post.objects.create(
			author=self.user,
			content="Pending",
			moderation_status=Post.MODERATION_PENDING,
		)
		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 0)

		Post.objects.create(
			author=self.user,
			content="Approved",
			moderation_status=Post.MODERATION_APPROVED,
		)
		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 1)

	def test_deleting_only_approved_post_unmarks_day(self):
		post = Post.objects.create(
			author=self.user,
			content="Only post",
			moderation_status=Post.MODERATION_APPROVED,
		)

		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 1)
		self.assertEqual(WeekCompletion.objects.filter(user=self.user).count(), 1)

		post.delete()

		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 0)
		self.assertEqual(WeekCompletion.objects.filter(user=self.user).count(), 0)

	def test_deleting_one_of_multiple_posts_same_day_keeps_completion(self):
		post_1 = Post.objects.create(
			author=self.user,
			content="P1",
			moderation_status=Post.MODERATION_APPROVED,
		)
		post_2 = Post.objects.create(
			author=self.user,
			content="P2",
			moderation_status=Post.MODERATION_APPROVED,
		)

		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 1)

		post_1.delete()

		self.assertTrue(Post.objects.filter(pk=post_2.pk).exists())
		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 1)

	def test_edit_status_approved_to_pending_removes_completion_when_no_other_post(self):
		post = Post.objects.create(
			author=self.user,
			content="To edit",
			moderation_status=Post.MODERATION_APPROVED,
		)
		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 1)

		post.moderation_status = Post.MODERATION_PENDING
		post.save(update_fields=["moderation_status"])

		self.assertEqual(WorkoutCompletion.objects.filter(user=self.user).count(), 0)


class RemoderatePostsCommandTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="mod_user", password="testpass123")

	@patch("posts.services.moderation_queue.moderate_post")
	def test_default_command_processes_only_pending(self, mock_moderate):
		pending_post = Post.objects.create(
			author=self.user,
			content="Pending",
			moderation_status=Post.MODERATION_PENDING,
		)
		approved_post = Post.objects.create(
			author=self.user,
			content="Approved",
			moderation_status=Post.MODERATION_APPROVED,
		)

		mock_moderate.return_value = (Post.MODERATION_APPROVED, "OK")
		call_command("remoderate_posts")

		pending_post.refresh_from_db()
		approved_post.refresh_from_db()

		self.assertEqual(pending_post.moderation_status, Post.MODERATION_APPROVED)
		self.assertEqual(approved_post.moderation_status, Post.MODERATION_APPROVED)
		self.assertEqual(mock_moderate.call_count, 1)

	@patch("posts.services.moderation_queue.moderate_post")
	def test_all_flag_remoderates_existing_approved_posts(self, mock_moderate):
		approved_post = Post.objects.create(
			author=self.user,
			content="Re-check me",
			moderation_status=Post.MODERATION_APPROVED,
		)

		mock_moderate.return_value = (Post.MODERATION_REJECTED, "Rule updated")
		call_command("remoderate_posts", "--all")

		approved_post.refresh_from_db()
		self.assertEqual(approved_post.moderation_status, Post.MODERATION_REJECTED)

	@patch("posts.services.moderation_queue.moderate_post")
	def test_post_stays_pending_when_moderation_is_unavailable(self, mock_moderate):
		pending_post = Post.objects.create(
			author=self.user,
			content="Still pending",
			moderation_status=Post.MODERATION_PENDING,
		)

		mock_moderate.return_value = (Post.MODERATION_PENDING, "API unavailable")
		call_command("remoderate_posts")

		pending_post.refresh_from_db()
		self.assertEqual(pending_post.moderation_status, Post.MODERATION_PENDING)


class ModerationApiKeyGateTests(TestCase):
	@override_settings(OPENAI_API_KEY="")
	def test_without_api_key_returns_pending_for_blocked_text(self):
		status, _ = moderate_post("sex")
		self.assertEqual(status, PENDING)
