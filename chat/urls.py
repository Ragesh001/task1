from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.thread_list_view, name='thread_list'),
    path('thread/<int:thread_id>/', views.thread_detail_view, name='thread_detail'),
    path('thread/<int:thread_id>/delete/', views.thread_delete_view, name='thread_delete'),
]
