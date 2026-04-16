from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Post


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
