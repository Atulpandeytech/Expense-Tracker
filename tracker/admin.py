from django.contrib import admin
from .models import Category, Income, Expense, MonthlyBudget


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('source', 'amount', 'date', 'user')
    list_filter = ('date', 'user')
    search_fields = ('source',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'category', 'date', 'user')
    list_filter = ('category', 'date', 'user')
    search_fields = ('title', 'description')


@admin.register(MonthlyBudget)
class MonthlyBudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'month', 'year', 'limit_amount')
    list_filter = ('month', 'year', 'user')

# Register your models here.
