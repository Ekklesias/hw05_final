import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django import forms
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

from posts.forms import PostForm
from posts.models import Post, Group, Comment, Follow

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpClass()
        cls.author_of_post = User.objects.create_user(username="TestAuthor")
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группы'
        )
        cls.group2 = Group.objects.create(
            title='Тестовая группа2',
            slug='test-group2',
            description='Тестовое описание группы2'
        )
        cls.image = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.image,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.author_of_post,
            group=cls.group,
            image=cls.uploaded
        )

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user_auth = User.objects.create_user(username='AuthUser')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user_auth)
        self.client_for_author_of_post = Client()
        self.client_for_author_of_post.force_login(self.author_of_post)

    def posts_check_all_fields(self, post):
        """Метод, проверяющий поля поста."""
        with self.subTest(post=post):
            self.assertEqual(post.id, self.post.id)
            self.assertEqual(post.text, self.post.text)
            self.assertEqual(post.author, self.post.author)
            self.assertEqual(post.group, self.post.group)
            self.assertEqual(post.image, self.post.image)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_page_names = {
            'posts/index.html': reverse('posts:index'),
            'posts/group_list.html': (
                reverse('posts:group_list', kwargs={'slug': 'test-group'})
            ),
            'posts/profile.html': (
                reverse('posts:profile', kwargs={'username': 'TestAuthor'})
            ),
            'posts/post_detail.html': (
                reverse('posts:post_detail', kwargs={'post_id': '1'})
            ),
            'posts/create.html': reverse('posts:post_create')
        }
        for template, reverse_name in templates_page_names.items():
            with self.subTest(template=template):
                response = self.client_for_author_of_post.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_page_show_correct_context(self):
        """Шаблон index с правильным контекстом"""
        response = self.client_for_author_of_post.get(reverse('posts:index'))
        self.posts_check_all_fields(response.context['page_obj'][0])
        self.assertIn('page_obj', response.context)

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list с правильным контекстом"""
        response = (self.client_for_author_of_post.get(
            reverse('posts:group_list',
                    kwargs={'slug': self.group.slug})))
        self.posts_check_all_fields(response.context['page_obj'][0])
        self.assertIn('page_obj', response.context)

    def test_profile_page_show_correct_context(self):
        """Шаблон profile с правильным контекстом"""
        response = (self.client_for_author_of_post.get(
            reverse('posts:profile',
                    kwargs={'username': self.author_of_post.username})))
        self.posts_check_all_fields(response.context['page_obj'][0])
        self.assertIn('page_obj', response.context)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail с правильным контекстом"""
        response = (self.client_for_author_of_post.get(
            reverse('posts:post_detail',
                    kwargs={'post_id': '1'})))
        self.posts_check_all_fields(response.context['post'])

    def test_create_page_show_correct_context(self):
        """Проверка форм создания и редактирования поста - create."""
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ChoiceField,
        }
        urls = (
            ('posts:post_create', None),
            ('posts:post_edit', (self.post.pk,)),
        )
        for url, slug in urls:
            reverse_name = reverse(url, args=slug)
            with self.subTest(reverse_name=reverse_name):
                response = self.client_for_author_of_post.get(reverse_name)
                self.assertIsInstance(response.context['form'], PostForm)
                for value, expected in form_fields.items():
                    with self.subTest(value=value):
                        form_field = response.context.get(
                            'form').fields.get(value)
                        self.assertIsInstance(form_field, expected)

    def test_post_on_index_group_profile_create(self):
        """Созданный пост появился в Группе, Профайле, Главной"""
        reverse_page_names_post = {
            reverse('posts:index'): self.group.slug,
            reverse('posts:profile', kwargs={
                'username': self.author_of_post}): self.group.slug,
            reverse('posts:group_list', kwargs={
                'slug': self.group.slug}): self.group.slug,
        }
        for value, expected in reverse_page_names_post.items():
            response = self.authorized_client.get(value)
            for object in response.context['page_obj']:
                post_group = object.group.slug
                with self.subTest(value=value):
                    self.assertEqual(post_group, expected)

    def test_post_not_in_other_group(self):
        """Пост не появился в другой группе"""
        response = self.authorized_client.get(
            reverse(
                'posts:group_list',
                kwargs={'slug': self.group2.slug}
            )
        )
        self.assertNotIn(self.post, response.context.get('page_obj'))
        group2 = response.context.get('group')
        self.assertNotEqual(group2, self.group)

    def test_comment_from_authorized_client(self):
        '''Проверяем, что коммент м оставить авторизованный юзер
        и коммент появляется на странице'''
        comments_count = Comment.objects.count()
        comments = {'text': 'Это тестовый комментарий'}
        self.client_for_author_of_post.post(
            reverse('posts:add_comment',
                    kwargs={
                        'post_id': self.post.pk
                    }),
            data=comments,
            follow=True,
        )
        response = self.client_for_author_of_post.get(
            reverse('posts:post_detail',
                    kwargs={
                        'post_id': self.post.pk
                    }),
        )
        self.assertContains(response, comments['text'])
        self.assertEqual(Comment.objects.count(), comments_count + 1)

    def test_comment_from_guest_client(self):
        """Проверяем, что гость не может комментировать"""
        comments = {'text': 'Это тестовый комментарий'}
        self.client.post(
            reverse('posts:add_comment',
                    kwargs={
                        'post_id': self.post.pk
                    }),
            data=comments,
            follow=True,
        )
        response = self.client.get(
            reverse('posts:post_detail',
                    kwargs={
                        'post_id': self.post.pk
                    }),
        )
        self.assertNotContains(response, comments['text'])

    def test_cache_index(self):
        """Тест, который проверяют работу кеша на главной странице"""
        response = self.client_for_author_of_post.get(reverse('posts:index'))
        count_of_orig_resp = response.content
        Post.objects.create(
            text="Ещё один пост",
            author=self.author_of_post
        )
        response_after_create_new_post = self.client_for_author_of_post.get(
            reverse('posts:index')
        )
        self.assertEqual(
            count_of_orig_resp,
            response_after_create_new_post.content
        )
        cache.clear()
        new_pesponse = self.client_for_author_of_post.get(
            reverse('posts:index')
        )
        new_count_of_posts = new_pesponse.content
        self.assertNotEqual(
            count_of_orig_resp,
            new_count_of_posts
        )


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author_of_post2 = User.objects.create_user(username="TestAuthor2")
        cls.group = Group.objects.create(
            title='Group for Paginator',
            slug='paginat',
            description='For test of paginator',
        )
        for test_post in range(1, 14):
            Post.objects.create(
                text=f'Text {test_post}',
                author=cls.author_of_post2,
                group=cls.group
            )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client_for_author_of_post = Client()
        self.client_for_author_of_post.force_login(self.author_of_post2)
        cache.clear()

    def test_first_page_contains_ten_records(self):
        response = self.client_for_author_of_post.get(reverse('posts:index'))
        self.assertEqual(
            len(response.context['page_obj']), settings.POSTS_AMOUNT
        )

    def test_second_page_contains_three_records(self):
        all_posts = Post.objects.count()
        response = self.client_for_author_of_post.get(
            reverse('posts:index') + '?page=2'
        )
        self.assertEqual(
            len(response.context['page_obj']),
            all_posts - settings.POSTS_AMOUNT
        )

    def test_page_contains_ten_and_3_posts(self):
        paginator_urls = (
            ('posts:index', None),
            ('posts:group_list', (self.group.slug,)),
            ('posts:profile', (self.author_of_post2.username,))
        )
        count_posts = (
            ('?page=1', settings.POSTS_AMOUNT),
            ('?page=2', settings.POSTS_AMOUNT2)
        )
        for address, args in paginator_urls:
            for page, count in count_posts:
                with self.subTest(page=page):
                    response = self.client_for_author_of_post.get(
                        reverse(address, args=args) + page
                    )
                    self.assertEqual(len(response.context['page_obj']), count)


class FollowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.follower = User.objects.create_user(username="TestFollower")
        cls.bloogger = User.objects.create_user(username="TestBlogger")
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группы2'
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.bloogger,
            group=cls.group,
        )

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        cache.clear()
        self.authorized_client_follower = Client()
        self.authorized_client_follower.force_login(self.follower)

    def test_follow_and_unfollow(self):
        """Авторизованный пользователь
        может подписываться на других пользователей и отписываться """
        self.authorized_client_follower.get(
            reverse('posts:profile_follow',
                    kwargs={'username': self.bloogger.username})
        )
        self.assertEqual(Follow.objects.all().count(), 1)
        self.authorized_client_follower.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': self.bloogger.username})
        )
        self.assertEqual(Follow.objects.all().count(), 0)

    def test_posts_in_line(self):
        """Новая запись пользователя появляется
        в ленте тех, кто на него подписан """
        self.authorized_client_follower.get(
            reverse('posts:profile_follow',
                    kwargs={'username': self.bloogger.username})
        )
        response = self.authorized_client_follower.get(
            reverse('posts:follow_index')
        )
        post = response.context['page_obj'][0].text
        self.assertEqual(post, self.post.text)

    def test_posts_not_in_line(self):
        """Новая запись не появляется в ленте тех, кто не подписан"""
        new_post = Post.objects.create(
            text='Новый тестовый пост',
            author=self.bloogger,
            group=self.group,
        )
        response = self.authorized_client_follower.get(
            reverse('posts:follow_index')
        )
        self.assertNotContains(response, new_post.text)
