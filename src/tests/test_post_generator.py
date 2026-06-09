from services.post_generator import CustomButton, PostDraft, PostGeneratorService, QualityButton


def test_post_generator_builds_html_and_deep_link_buttons() -> None:
    service = PostGeneratorService("https://t.me/linka_bot?start=")

    post = service.generate(
        PostDraft(
            title="Movie <Title>",
            description="Choose quality",
            qualities=[
                QualityButton(label="480p", token="quality_480_123"),
                QualityButton(label="1080p", token="quality_1080_123", premium=True),
            ],
            custom_buttons=[CustomButton(label="Channel", url="https://t.me/example")],
        )
    )

    assert "<b>Movie &lt;Title&gt;</b>" in post.text
    assert post.buttons[0][0]["url"] == "https://t.me/linka_bot?start=quality_480_123"
    assert post.buttons[1][0]["text"] == "1080p VIP"
    assert post.buttons[2][0]["url"] == "https://t.me/example"
