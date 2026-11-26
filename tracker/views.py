from datetime import date
from calendar import month_name
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import Lower, Trim
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ExpenseForm, IncomeForm, MonthlyBudgetForm
from .models import Category, Expense, Income, MonthlyBudget


DEFAULT_CATEGORIES = [
    ('Food', 'food'), ('Transportation', 'transportation'),
    ('Education', 'education'), ('Shopping', 'shopping'),
    ('Entertainment', 'entertainment'), ('Healthcare', 'healthcare'),
    ('Other', 'other'), ('Grocery', 'grocery'),
    ('Electricity Bill', 'electricity-bill'), ('Room Rent', 'room-rent'),
    ('Other Household Expenses', 'other-household-expenses'),
]


def finance_chat_reply(message, total_income, total_expenses, monthly_spend, budget, budget_usage, category_totals):
    """Answer common finance questions using the current user's private totals."""
    message = message.lower().strip()
    balance = total_income - total_expenses
    category_name = category_totals[0]['category__name'] if category_totals else None
    category_amount = category_totals[0]['total'] if category_totals else Decimal('0')

    if not message:
        return 'Tell me what you want to improve, such as saving more, reducing food spending, or understanding your budget.'
    if any(word in message for word in ('hello', 'hi', 'hey')):
        return 'Hi! I am your Finance Mentor. Ask me why your savings are low, where you spend the most, or how to make a realistic monthly plan.'
    if any(word in message for word in ('saving', 'save', 'savings')):
        if total_income <= 0:
            return 'I need at least one income record before I can calculate a realistic savings target. Add your income first, then ask me again.'
        target = (total_income * Decimal('0.2')).quantize(Decimal('0.01'))
        if balance <= 0:
            return f'Your recorded expenses are Rs. {abs(balance):,.2f} higher than your income. First reduce spending below income; then aim to save Rs. {target:,.2f}, or 20% of your recorded income.'
        return f'You currently have Rs. {balance:,.2f} left from recorded income. A realistic first target is Rs. {target:,.2f} (20% of income). Move that amount to savings when income arrives, then manage the remaining balance.'
    if any(word in message for word in ('where', 'category', 'spend most', 'largest')):
        if not category_name:
            return 'There are no expense records yet. Add a few expenses and I can identify your biggest spending category.'
        saving = (category_amount * Decimal('0.1')).quantize(Decimal('0.01'))
        return f'Your largest current category is {category_name} at Rs. {category_amount:,.2f}. A practical first step is to reduce it by 10%, which could save about Rs. {saving:,.2f}.'
    if any(word in message for word in ('budget', 'limit', 'remaining')):
        if not budget:
            return 'You have not set a monthly budget yet. Open Budgets, set a limit based on your income, and I can help you track it.'
        if budget_usage >= 100:
            return f'You have exceeded this month’s budget by Rs. {abs(budget.limit_amount - monthly_spend):,.2f}. Stop non-essential spending, review your largest category, and set a daily limit for the remaining days.'
        return f'You have used {budget_usage:,.1f}% of your monthly budget and have Rs. {budget.limit_amount - monthly_spend:,.2f} remaining. Keep at least 10% as a buffer for unexpected costs.'
    if any(word in message for word in ('plan', 'manage', 'help', 'not saving', 'not save')):
        if balance <= 0:
            return 'Let us start with a recovery plan: list essential expenses, pause non-essential purchases, set a weekly spending cap, and record every expense. Once your balance is positive, automate a small saving first.'
        return f'Here is a simple plan: save 20% of income first, reserve essentials next, set a weekly cap for {category_name or "your largest category"}, and review your dashboard every Sunday. Your current available balance is Rs. {balance:,.2f}.'
    return f'Based on your dashboard, income is Rs. {total_income:,.2f}, expenses are Rs. {total_expenses:,.2f}, and your balance is Rs. {balance:,.2f}. Ask me “how can I save more?”, “where do I spend the most?”, or “how is my budget?”'


def ensure_categories():
    for name, slug in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={'slug': slug})


@login_required
def dashboard(request):
    ensure_categories()
    today = date.today()
    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)
    monthly_expenses = expenses.filter(date__year=today.year, date__month=today.month)
    total_income = incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    monthly_spend = monthly_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    budget = MonthlyBudget.objects.filter(
        user=request.user, month=today.month, year=today.year
    ).first()
    budget_usage = None
    budget_remaining = None
    if budget:
        budget_usage = (monthly_spend / budget.limit_amount * 100).quantize(Decimal('0.1'))
        budget_remaining = budget.limit_amount - monthly_spend
    expense_totals = expenses.order_by().annotate(
        normalized_title=Lower(Trim('title'))
    ).values('normalized_title').annotate(
        title=Min('title'),
        total=Sum('amount'),
        category_count=Count('category', distinct=True),
        category_name=Min('category__name'),
    ).order_by('-total', 'title')[:8]
    category_totals = list(
        monthly_expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')
    )
    return render(request, 'tracker/dashboard.html', {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': total_income - total_expenses,
        'monthly_spend': monthly_spend,
        'budget': budget,
        'budget_usage': budget_usage,
        'budget_remaining': budget_remaining,
        'expense_totals': expense_totals,
        'category_totals': category_totals,
        'today': today,
    })


@login_required
def income_list(request):
    form = IncomeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        income = form.save(commit=False)
        income.user = request.user
        income.save()
        messages.success(request, 'Income added successfully.')
        return redirect('income_list')
    incomes = Income.objects.filter(user=request.user)
    return render(request, 'tracker/income_list.html', {'incomes': incomes, 'form': form})


@login_required
def income_update(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    form = IncomeForm(request.POST or None, instance=income)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Income updated successfully.')
        return redirect('income_list')
    return render(request, 'tracker/income_form.html', {'form': form, 'income': income})


@login_required
def income_delete(request, pk):
    income = get_object_or_404(Income, pk=pk, user=request.user)
    if request.method == 'POST':
        income.delete()
        messages.success(request, 'Income deleted successfully.')
        return redirect('income_list')
    return render(request, 'tracker/confirm_delete.html', {'object': income, 'cancel_url': 'income_list'})


@login_required
def expense_list(request):
    ensure_categories()
    expenses = Expense.objects.filter(user=request.user)
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    month_value = request.GET.get('month', '').strip()
    if query:
        expenses = expenses.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if category_slug:
        expenses = expenses.filter(category__slug=category_slug)
    if month_value:
        expenses = expenses.filter(date__month=month_value)
    return render(request, 'tracker/expense_list.html', {
        'expenses': expenses,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category_slug,
        'selected_month': month_value,
    })


@login_required
def expense_create(request):
    ensure_categories()
    form = ExpenseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        messages.success(request, 'Expense added successfully.')
        return redirect('expense_detail', pk=expense.pk)
    return render(request, 'tracker/expense_form.html', {'form': form})


@login_required
def expense_detail(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return render(request, 'tracker/expense_detail.html', {'expense': expense})


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Expense updated successfully.')
        return redirect('expense_detail', pk=expense.pk)
    return render(request, 'tracker/expense_form.html', {'form': form, 'expense': expense})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('expense_list')
    return render(request, 'tracker/confirm_delete.html', {'object': expense, 'cancel_url': 'expense_detail', 'object_id': pk})


@login_required
def expense_by_category(request, slug):
    ensure_categories()
    category = get_object_or_404(Category, slug=slug)
    expenses = Expense.objects.filter(user=request.user, category=category)
    return render(request, 'tracker/expense_list.html', {
        'expenses': expenses, 'categories': Category.objects.all(),
        'selected_category': slug, 'query': '', 'selected_month': '',
    })


@login_required
def expense_by_month(request, month_name_value):
    month_number = next((i for i in range(1, 13) if month_name[i].lower() == month_name_value.lower()), None)
    expenses = Expense.objects.none() if month_number is None else Expense.objects.filter(user=request.user, date__month=month_number)
    return render(request, 'tracker/expense_list.html', {
        'expenses': expenses, 'categories': Category.objects.all(),
        'selected_category': '', 'query': '', 'selected_month': str(month_number or ''),
    })


@login_required
def budgets(request):
    ensure_categories()
    today = date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    form = MonthlyBudgetForm(
        request.POST or None,
        initial={'month': month, 'year': year},
    )
    if request.method == 'POST' and form.is_valid():
        budget = form.save(commit=False)
        budget.user = request.user
        existing = MonthlyBudget.objects.filter(
            user=request.user, month=budget.month, year=budget.year
        ).first()
        if existing:
            existing.limit_amount = budget.limit_amount
            existing.save()
        else:
            budget.save()
        messages.success(request, 'Monthly budget saved.')
        return redirect(f"{reverse('budgets')}?month={budget.month}&year={budget.year}")
    budget = MonthlyBudget.objects.filter(user=request.user, month=month, year=year).first()
    spent = Expense.objects.filter(
        user=request.user, date__month=month, date__year=year
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    usage = ((spent / budget.limit_amount * 100).quantize(Decimal('0.1'))) if budget else None
    monthly_expense_totals = {
        (row['date__year'], row['date__month']): row['total']
        for row in Expense.objects.filter(user=request.user).order_by().values(
            'date__year', 'date__month'
        ).annotate(total=Sum('amount'))
    }
    budget_periods = []
    for saved_budget in MonthlyBudget.objects.filter(user=request.user).order_by('-year', '-month'):
        period_spent = monthly_expense_totals.get(
            (saved_budget.year, saved_budget.month), Decimal('0')
        )
        month_label = (
            month_name[saved_budget.month]
            if 1 <= saved_budget.month <= 12
            else f"Month {saved_budget.month}"
        )
        budget_periods.append({
            'month': saved_budget.month,
            'month_name': month_label,
            'year': saved_budget.year,
            'limit': saved_budget.limit_amount,
            'spent': period_spent,
            'remaining': saved_budget.limit_amount - period_spent,
            'usage': (
                period_spent / saved_budget.limit_amount * 100
            ).quantize(Decimal('0.1')),
        })
    return render(request, 'tracker/budgets.html', {
        'form': form, 'budget': budget, 'usage': usage, 'month': month, 'year': year,
        'budget_periods': budget_periods,
    })


@login_required
def budget_month_detail(request, year, month):
    budget = get_object_or_404(
        MonthlyBudget, user=request.user, year=year, month=month
    )
    incomes = Income.objects.filter(
        user=request.user, date__year=year, date__month=month
    )
    expenses = Expense.objects.filter(
        user=request.user, date__year=year, date__month=month
    ).select_related('category')
    total_income = incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    remaining = budget.limit_amount - total_expenses
    usage = (total_expenses / budget.limit_amount * 100).quantize(Decimal('0.1'))
    return render(request, 'tracker/budget_month_detail.html', {
        'budget': budget,
        'month_name': month_name[month],
        'incomes': incomes,
        'expenses': expenses,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': total_income - total_expenses,
        'remaining': remaining,
        'usage': usage,
    })


@login_required
def annual_report(request, year):
    year = int(year)
    income_rows = []
    expense_rows = []
    for month in range(1, 13):
        monthly_income = Income.objects.filter(
            user=request.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_expenses = Expense.objects.filter(
            user=request.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        income_rows.append(float(monthly_income))
        expense_rows.append(float(monthly_expenses))
    category_totals = Expense.objects.filter(
        user=request.user, date__year=year
    ).values('category__name').annotate(total=Sum('amount')).order_by('-total')
    category_rows = [
        {'label': row['category__name'], 'total': float(row['total'])}
        for row in category_totals
    ]
    budget_limits = [None] * 12
    for monthly_budget in MonthlyBudget.objects.filter(user=request.user, year=year):
        if 1 <= monthly_budget.month <= 12:
            budget_limits[monthly_budget.month - 1] = float(monthly_budget.limit_amount)
    report_data = {
        'months': [month_name[i][:3] for i in range(1, 13)],
        'income': income_rows,
        'expenses': expense_rows,
        'budget': budget_limits,
        'categories': category_rows,
    }
    return render(request, 'tracker/reports.html', {
        'year': year,
        'report_data': report_data,
    })


@login_required
def chart_data_json(request):
    expenses = Expense.objects.filter(user=request.user)
    category_data = expenses.values('category__name').annotate(total=Sum('amount')).order_by('category__name')
    current_year = date.today().year
    monthly_income = [float(Income.objects.filter(
        user=request.user, date__year=current_year, date__month=m
    ).aggregate(total=Sum('amount'))['total'] or 0) for m in range(1, 13)]
    monthly_expense = [float(Expense.objects.filter(
        user=request.user, date__year=current_year, date__month=m
    ).aggregate(total=Sum('amount'))['total'] or 0) for m in range(1, 13)]
    return JsonResponse({
        'labels': [row['category__name'] for row in category_data],
        'data': [float(row['total']) for row in category_data],
        'months': [month_name[i][:3] for i in range(1, 13)],
        'income': monthly_income,
        'expenses': monthly_expense,
    })


@login_required
def mentor_chat(request):
    if request.method == 'GET':
        return render(request, 'tracker/mentor_chat.html')
    if request.method != 'POST':
        return JsonResponse({'error': 'Only GET and POST requests are supported.'}, status=405)
    message = request.POST.get('message', '')
    today = date.today()
    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)
    total_income = incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    monthly_spend = expenses.filter(date__year=today.year, date__month=today.month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    budget = MonthlyBudget.objects.filter(user=request.user, month=today.month, year=today.year).first()
    budget_usage = ((monthly_spend / budget.limit_amount * 100).quantize(Decimal('0.1'))) if budget else None
    category_totals = list(
        expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')
    )
    reply = finance_chat_reply(
        message, total_income, total_expenses, monthly_spend, budget, budget_usage, category_totals
    )
    return JsonResponse({'reply': reply})


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)
