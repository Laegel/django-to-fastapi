from django_to_fastapi.routes import Route, get_modules_from_routes, get_routes


def test_extract_view():
    definition = """
urlpatterns = [
    path('posts/create', CreatePostsView.as_view()),
    path('posts/unpublish', UnpublishPostsView.as_view()),
    path('posts/delete', DeletePostsView.as_view()),
    path('posts', PostsView.as_view()),
    path('last', LastView().as_view()),
    path('auth/signin', signin),
]
    """
    expected_routes = [
        {
            "path": "/posts/create",
            "view": "CreatePostsView",
        },
        {
            "path": "/posts/unpublish",
            "view": "UnpublishPostsView",
        },
        {
            "path": "/posts/delete",
            "view": "DeletePostsView",
        },
        {
            "path": "/posts",
            "view": "PostsView",
        },
        {
            "path": "/last",
            "view": "LastView",
        },
        {
            "path": "/auth/signin",
            "view": "signin",
        },
    ]
    routes = get_routes(definition)
    assert routes == [Route(**route) for route in expected_routes]


def test_get_module():
    definition = """
from frontend_api.endpoints.posts import CreatePostsView, UnpublishPostsView
from frontend_api.endpoints.auth import signin, signup
    """
    routes = (
        Route(
            path="posts/create",
            view="CreatePostsView",
        ),
        Route(
            path="auth/signin",
            view="signin",
        ),
    )
    expected = ["frontend_api/endpoints/posts", "frontend_api/endpoints/auth"]
    assert get_modules_from_routes(definition, routes) == expected
