from django.urls import path

from . import criteria_views, views

app_name = "achievements"

urlpatterns = [
    path("yutuqlar/", views.my_list, name="my_list"),
    path("yutuqlar/yangi/", views.create, name="create"),
    path("yutuqlar/<int:pk>/", views.detail, name="detail"),
    path("yutuqlar/<int:pk>/tahrir/", views.edit, name="edit"),
    path("yutuqlar/<int:pk>/ochirish/", views.delete, name="delete"),
    path("fayl/<int:pk>/", views.file_view, name="file"),
    path("tekshiruv/", views.queue, name="queue"),
    path("baholash/", views.manual_scores, name="manual"),
    path("sozlamalar/mezonlar/", criteria_views.criteria_list, name="criteria"),
    path("sozlamalar/mezonlar/<int:pk>/", criteria_views.criterion_edit, name="criterion_edit"),
]
