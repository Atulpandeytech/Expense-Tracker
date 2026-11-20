from datetime import date
from calendar import month_name
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseForm, IncomeForm, MonthlyBudgetForm
from .models import Category, Expense, Income, MonthlyBudget


DEFAULT_CATEGORIES = [
    ('Food', 'food'), ('Transportation', 'transportation'),
    ('Education', 'education'), ('Shopping', 'shopping'),
    ('Entertainment', 'entertainment'), ('Healthcare', 'healthcare'),
    ('Other', 'other'),
]


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
        'recent_expenses': expenses[:8],
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
    form = MonthlyBudgetForm(request.POST or None)
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
        return redirect('budgets')
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    budget = MonthlyBudget.objects.filter(user=request.user, month=month, year=year).first()
    spent = Expense.objects.filter(
        user=request.user, date__month=month, date__year=year
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    remaining = (budget.limit_amount - spent) if budget else None
    usage = ((spent / budget.limit_amount * 100).quantize(Decimal('0.1'))) if budget else None
    return render(request, 'tracker/budgets.html', {
        'form': form, 'budget': budget, 'spent': spent,
        'remaining': remaining, 'usage': usage, 'month': month, 'year': year,
    })


@login_required
def annual_report(request, year):
    year = int(year)
    income_rows = []
    expense_rows = []
    category_rows = []
    for month in range(1, 13):
        income_rows.append(Income.objects.filter(
            user=request.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0)
        expense_rows.append(Expense.objects.filter(
            user=request.user, date__year=year, date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0)
    category_rows = list(Expense.objects.filter(
        user=request.user, date__year=year
    ).values('category__name').annotate(total=Sum('amount')).order_by('-total'))
    return render(request, 'tracker/reports.html', {
        'year': year,
        'months': [month_name[i][:3] for i in range(1, 13)],
        'income_rows': income_rows,
        'expense_rows': expense_rows,
        'category_rows': category_rows,
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


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)
