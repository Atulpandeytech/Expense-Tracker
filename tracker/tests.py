from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from datetime import date
from decimal import Decimal
from .models import Category, Expense, Income, MonthlyBudget


class StudentExpenseTrackerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='StrongPass123!')
        self.category = Category.objects.create(name='Food', slug='food')

    def test_auth_redirect(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_expense_is_user_scoped(self):
        other = User.objects.create_user(username='other', password='StrongPass123!')
        expense = Expense.objects.create(
            user=other, category=self.category, title='Bus fare',
            amount=Decimal('250.00'), date=date.today()
        )
        self.client.login(username='student', password='StrongPass123!')
        response = self.client.get(reverse('expense_detail', args=[expense.pk]))
        self.assertEqual(response.status_code, 404)

    def test_add_expense_and_chart_json(self):
        self.client.login(username='student', password='StrongPass123!')
        response = self.client.post(reverse('expense_create'), {
            'title': 'Lunch', 'amount': '250.00', 'category': self.category.pk,
            'date': date.today().isoformat(), 'description': 'Campus lunch'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Expense.objects.filter(user=self.user, title='Lunch').exists())
        json_response = self.client.get(reverse('chart_data_json'))
        self.assertEqual(json_response.status_code, 200)
        self.assertIn('data', json_response.json())

    def test_budget_creation(self):
        self.client.login(username='student', password='StrongPass123!')
        today = date.today()
        response = self.client.post(reverse('budgets'), {
            'month': today.month, 'year': today.year, 'limit_amount': '5000.00'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MonthlyBudget.objects.filter(user=self.user).exists())
