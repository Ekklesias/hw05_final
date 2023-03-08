from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.core.cache import cache

from posts.models import Post, Group

User = get_user_model()


class StaticURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author_of_post = User.objects.create_user(username="TestAuthor")
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группы'
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.author_of_post,
            group=cls.group
        )
        cls.templates_url_names = {
            '/': 'posts/index.html',
            f'/group/{cls.group.slug}/': 'posts/group_list.html',
            f'/profile/{cls.author_of_post}/': 'posts/profile.html',
            f'/posts/{cls.post.pk}/': 'posts/post_detail.html',
            f'/posts/{cls.post.pk}/edit/': 'posts/create.html',
            '/create/': 'posts/create.html',
        }
        cls.temp_urls_status_code = {
            '/': HTTPStatus.OK,
            f'/group/{cls.group.slug}/': HTTPStatus.OK,
            f'/profile/{cls.author_of_post}/': HTTPStatus.OK,
            f'/posts/{cls.post.pk}/': HTTPStatus.OK,
            f'/posts/{cls.post.pk}/edit/': HTTPStatus.OK,
            '/create/': HTTPStatus.OK,
        }

    def setUp(self):
        self.user_auth = User.objects.create_user(username='TestAuth')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user_auth)
        self.client_for_author_of_post = Client()
        self.client_for_author_of_post.force_login(self.author_of_post)
        cache.clear()

    def test_unexisting_page_correct_status(self):
        """Страница по адресу 'unexisting_page' вернёт ошибку 404."""
        response = self.client.get('/unexisting_page/').status_code
        self.assertEqual(response, HTTPStatus.NOT_FOUND)

    def test_client_for_author_of_post_status_code(self):
        """Проверим, что все страницы доступны автору."""
        for address, status_code in self.temp_urls_status_code.items():
            if address != '/unexisting_page/':
                with self.subTest(address=address):
                    response = self.client_for_author_of_post.get(
                        address).status_code
                    self.assertEqual(response, status_code)

    def test_authorized_client_status_code(self):
        """Проверим, что все страницы доступны НЕавтору,
        кроме edit. C edit редирект на post_detail"""
        edit_url = f'/posts/{self.post.pk}/'
        for address, status_code in self.temp_urls_status_code.items():
            if address != f'/posts/{self.post.pk}/edit/':
                with self.subTest(address=address):
                    response = self.authorized_client.get(address).status_code
                    self.assertEqual(response, status_code)
            else:
                response = self.authorized_client.get(address)
                self.assertRedirects(response, edit_url)

    def test_guest_client_status_code(self):
        """Проверим, что все страницы доступны анониму,
        кроме edit и create. C ними редирект на авторизацию"""
        auth_url = '/auth/login/?next='
        for address, status_code in self.temp_urls_status_code.items():
            if (address != f'/posts/{self.post.pk}/edit/'
                    and address != '/create/'):
                with self.subTest(address=address):
                    response = self.client.get(address).status_code
                    self.assertEqual(response, status_code)
            else:
                response = self.client.get(address)
                self.assertRedirects(response, f'{auth_url}{address}')

    def test_urls_uses_correct_template1(self):
        """URL-адрес использует соответствующий шаблон."""
        for address, template in self.templates_url_names.items():
            if (address != f'/posts/{self.post.pk}/edit/'
                    and address != '/create/'):
                with self.subTest(address=address):
                    response = self.authorized_client.get(address)
                    self.assertTemplateUsed(response, template)
            elif address == f'/posts/{self.post.pk}/edit/':
                response = self.client_for_author_of_post.get(address)
                self.assertTemplateUsed(response, template)
            else:
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_page_not_found_404(self):
        response = self.authorized_client.get('/oopss')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertTemplateUsed(response, 'core/404.html')
