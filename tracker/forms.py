from django import forms
from .models import Income, Expense, MonthlyBudget


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class IncomeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Income
        fields = ['source', 'amount', 'date']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class ExpenseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class MonthlyBudgetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MonthlyBudget
        fields = ['month', 'year', 'limit_amount']
