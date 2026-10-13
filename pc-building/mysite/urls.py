from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import RedirectView

admin.site.site_header = 'CleanByte Admin'
admin.site.site_title = 'CleanByte Admin'
admin.site.index_title = 'Store management'

urlpatterns = [
    path('', include('store.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    # allauth is only used for Google sign-in. Its own username/password pages would be a second,
    # unstyled way to sign up or log in, so send them to the store's pages instead.
    path('auth/login/', RedirectView.as_view(pattern_name='login', query_string=True)),
    path('auth/signup/', RedirectView.as_view(pattern_name='signup', query_string=True)),
    path('auth/logout/', RedirectView.as_view(pattern_name='product_list')),
    path('auth/email/', RedirectView.as_view(pattern_name='product_list')),
    re_path(r'^auth/password/', RedirectView.as_view(pattern_name='password_reset')),
    path('auth/', include('allauth.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
