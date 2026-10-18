from commons_audio import normalize_file


def page(license_name="CC BY-SA 4.0", url="https://upload.wikimedia.org/audio.ogg"):
    return {
        "title": "File:Bird.ogg",
        "imageinfo": [{"url": url, "extmetadata": {
            "LicenseShortName": {"value": license_name},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
            "Artist": {"value": "<a href='/wiki/User:Recordist'>Recordist</a>"},
            "ImageDescription": {"value": "Bird call"},
        }}],
    }


def test_commons_audio_keeps_attribution_and_source():
    result = normalize_file(page())
    assert result["artist"] == "Recordist"
    assert result["license"] == "CC BY-SA 4.0"
    assert result["audio_url"].startswith("https://upload.wikimedia.org/")
    assert result["page_url"].startswith("https://commons.wikimedia.org/wiki/")


def test_commons_audio_ignores_unsupported_or_unlicensed_recordings():
    assert normalize_file(page("CC BY-NC 4.0")) is None
    assert normalize_file(page(url="http://example.org/audio.ogg")) is None
