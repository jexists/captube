from app.services.urls import normalize_youtube_url


def test_normalize_watch_url_removes_playlist_parameters():
    url = "https://www.youtube.com/watch?v=OkTyY28XMuQ&list=PLT27bttR-0699T4Cu8HfsiCN3hArUguBa&index=65"

    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=OkTyY28XMuQ"


def test_normalize_watch_url_removes_timestamp_parameter():
    url = "https://www.youtube.com/watch?v=zpMHGnSAusI&t=338s"

    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=zpMHGnSAusI"


def test_normalize_short_url_to_watch_url():
    url = "https://youtu.be/OkTyY28XMuQ?si=abc123"

    assert normalize_youtube_url(url) == "https://www.youtube.com/watch?v=OkTyY28XMuQ"


def test_normalize_non_youtube_url_returns_original():
    url = "https://example.com/watch?v=OkTyY28XMuQ&list=nope"

    assert normalize_youtube_url(url) == url
