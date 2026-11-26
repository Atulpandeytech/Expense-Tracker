from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from datetime import date
from decimal import Decimal
from .models import Category, Expense, Income, MonthlyBudget
from .views import finance_chat_reply


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

    def test_expense_form_includes_household_categories(self):
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse('expense_create'))

        self.assertEqual(response.status_code, 200)
        category_names = set(
            response.context['form'].fields['category'].queryset.values_list('name', flat=True)
        )
        self.assertTrue({
            'Grocery',
            'Electricity Bill',
            'Room Rent',
            'Other Household Expenses',
        }.issubset(category_names))

    def test_annual_report_provides_numeric_monthly_chart_data(self):
        today = date.today()
        Income.objects.create(
            user=self.user, source='Scholarship', amount=Decimal('3000.00'), date=today,
        )
        Expense.objects.create(
            user=self.user, category=self.category, title='Books',
            amount=Decimal('750.00'), date=today,
        )
        MonthlyBudget.objects.create(
            user=self.user, month=today.month, year=today.year,
            limit_amount=Decimal('5000.00'),
        )
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse('annual_report', kwargs={'year': today.year}))

        self.assertEqual(response.status_code, 200)
        report_data = response.context['report_data']
        self.assertEqual(report_data['income'][today.month - 1], 3000.0)
        self.assertEqual(report_data['expenses'][today.month - 1], 750.0)
        self.assertEqual(report_data['budget'][today.month - 1], 5000.0)
        self.assertIsNone(report_data['budget'][today.month % 12])
        self.assertEqual(report_data['categories'][0], {'label': 'Food', 'total': 750.0})
        self.assertContains(response, 'report-data')
        self.assertContains(response, "label: 'Monthly Budget'")

    def test_budget_creation(self):
        self.client.login(username='student', password='StrongPass123!')
        today = date.today()
        response = self.client.post(reverse('budgets'), {
            'month': today.month, 'year': today.year, 'limit_amount': '5000.00'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'month={today.month}&year={today.year}', response['Location'])
        self.assertTrue(MonthlyBudget.objects.filter(user=self.user).exists())

    def test_dashboard_does_not_show_monthly_budget_history(self):
        today = date.today()
        MonthlyBudget.objects.create(
            user=self.user, month=today.month, year=today.year,
            limit_amount=Decimal('5000.00'),
        )
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Your budgets')
        self.assertNotContains(response, 'View details')

    def test_dashboard_groups_same_expense_title_across_months(self):
        today = date.today()
        Expense.objects.create(
            user=self.user, category=self.category, title='Grocery',
            amount=Decimal('10000.00'), date=today,
        )
        Expense.objects.create(
            user=self.user, category=self.category, title='grocery',
            amount=Decimal('10000.00'), date=date(today.year - 1, today.month, 1),
        )
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        grocery = next(
            item for item in response.context['expense_totals']
            if item['title'].lower() == 'grocery'
        )
        self.assertEqual(grocery['total'], Decimal('20000.00'))
        self.assertEqual(grocery['category_count'], 1)

    def test_budget_page_lists_future_month_budget_progress(self):
        today = date.today()
        month = 1 if today.month == 12 else today.month + 1
        year = today.year + 1 if today.month == 12 else today.year
        MonthlyBudget.objects.create(
            user=self.user, month=month, year=year,
            limit_amount=Decimal('25000.00'),
        )
        Expense.objects.create(
            user=self.user, category=self.category, title='Rent',
            amount=Decimal('16000.00'), date=date(year, month, 15),
        )
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse('budgets'), {'month': month, 'year': year})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Monthly Budget Progress')
        self.assertContains(response, 'Monthly budgets')
        self.assertContains(response, reverse('budget_month_detail', args=[year, month]))
        self.assertContains(response, f'{date(year, month, 1).strftime("%B")} {year}')
        self.assertContains(response, 'Rs. 9,000.00')
        self.assertContains(response, '64.0%')
        period = response.context['budget_periods'][0]
        self.assertEqual(period['remaining'], Decimal('9000.00'))
        self.assertEqual(period['spent'], Decimal('16000.00'))

    def test_budget_month_detail_lists_only_that_users_month_transactions(self):
        today = date.today()
        MonthlyBudget.objects.create(
            user=self.user, month=today.month, year=today.year,
            limit_amount=Decimal('5000.00'),
        )
        Income.objects.create(
            user=self.user, source='Scholarship', amount=Decimal('10000.00'), date=today,
        )
        Expense.objects.create(
            user=self.user, category=self.category, title='Books',
            amount=Decimal('1500.00'), date=today, description='Course materials',
        )
        other_month = date(today.year, 12, 1) if today.month != 12 else date(today.year, 1, 1)
        Expense.objects.create(
            user=self.user, category=self.category, title='Other month expense',
            amount=Decimal('300.00'), date=other_month,
        )
        other_user = User.objects.create_user(username='other', password='StrongPass123!')
        Income.objects.create(
            user=other_user, source='Private income', amount=Decimal('500.00'), date=today,
        )
        self.client.login(username='student', password='StrongPass123!')

        response = self.client.get(reverse(
            'budget_month_detail', args=[today.year, today.month]
        ))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scholarship')
        self.assertContains(response, 'Books')
        self.assertContains(response, 'Course materials')
        self.assertNotContains(response, 'Other month expense')
        self.assertNotContains(response, 'Private income')
        self.assertEqual(response.context['total_income'], Decimal('10000.00'))
        self.assertEqual(response.context['total_expenses'], Decimal('1500.00'))

    def test_finance_chat_uses_user_totals(self):
        reply = finance_chat_reply(
            'How can I save more?', Decimal('10000'), Decimal('9000'),
            Decimal('4000'), None, None, [],
        )
        self.assertIn('Rs. 1,000.00', reply)
