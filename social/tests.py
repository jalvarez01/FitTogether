from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from posts.models import Post
from .models import Follow


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class FriendshipVisibilityTests(TestCase):
	def setUp(self):
		self.user_a = User.objects.create_user(username="alice", password="testpass123")
		self.user_b = User.objects.create_user(username="bob", password="testpass123")

		Follow.objects.create(follower=self.user_a, following=self.user_b, status=Follow.ACCEPTED)
		Follow.objects.create(follower=self.user_b, following=self.user_a, status=Follow.ACCEPTED)

		self.post_a = Post.objects.create(author=self.user_a, content="alice-visible-post")
		self.post_b = Post.objects.create(author=self.user_b, content="bob-visible-post")

	def test_posts_not_visible_in_feed_after_remove_friend(self):
		self.client.force_login(self.user_a)
		before = self.client.get(reverse("social:feed"))
		self.assertContains(before, "bob-visible-post")

		remove_response = self.client.post(reverse("social:remove_friend", args=[self.user_b.id]))
		self.assertEqual(remove_response.status_code, 302)

		self.assertFalse(
			Follow.objects.filter(follower=self.user_a, following=self.user_b, status=Follow.ACCEPTED).exists()
		)
		self.assertFalse(
			Follow.objects.filter(follower=self.user_b, following=self.user_a, status=Follow.ACCEPTED).exists()
		)

		after_a = self.client.get(reverse("social:feed"))
		self.assertNotContains(after_a, "bob-visible-post")

		self.client.force_login(self.user_b)
		after_b = self.client.get(reverse("social:feed"))
		self.assertNotContains(after_b, "alice-visible-post")

	def test_posts_not_visible_in_profile_after_remove_friend(self):
		self.client.force_login(self.user_a)
		before = self.client.get(reverse("social:user_profile", args=[self.user_b.username]))
		self.assertContains(before, "bob-visible-post")

		self.client.post(reverse("social:remove_friend", args=[self.user_b.id]))

		after = self.client.get(reverse("social:user_profile", args=[self.user_b.username]))
		self.assertNotContains(after, "bob-visible-post")
		self.assertEqual(len(after.context["posts"]), 0)
