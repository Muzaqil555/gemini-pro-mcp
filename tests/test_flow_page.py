from gemini_pro_mcp.flow import page as page_lib


class FakeKeyboard:
    def __init__(self):
        self.pressed = []
        self.typed = []

    async def press(self, key):
        self.pressed.append(key)

    async def type(self, text, delay=0):
        self.typed.append(text)


class FakeTarget:
    first = property(lambda self: self)

    async def count(self):
        return 1

    async def get_attribute(self, name):
        return None

    async def evaluate(self, script):
        return True  # a contenteditable prompt box

    async def click(self, timeout=None):
        pass


class FakeFrame:
    def locator(self, selector):
        return FakeTarget()


class FakePage:
    url = "https://flow.google.com/project/1"

    def __init__(self):
        self.keyboard = FakeKeyboard()
        self.main_frame = FakeFrame()
        self.frames = [self.main_frame]

    async def wait_for_timeout(self, ms):
        pass


async def test_replace_selects_all_with_the_key_of_the_platform():
    # Control+A only moves the cursor on macOS, so the text was added, not replaced.
    page = FakePage()
    await page_lib._act(page, "3", "replace", "new prompt", None)
    assert page.keyboard.pressed == ["ControlOrMeta+A", "Delete"]
    assert page.keyboard.typed == ["new prompt"]
