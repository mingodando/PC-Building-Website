from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'CleanByte Admin'
admin.site.site_title = 'CleanByte Admin'
admin.site.index_title = 'Store management'

urlpatterns = [
    path('', include('store.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('auth/', include('allauth.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
