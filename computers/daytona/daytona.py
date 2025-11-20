# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import time
import base64
import termcolor
from typing import Literal, Optional
from ..computer import Computer, EnvState
from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams, DaytonaError, ScreenshotOptions

DAYTONA_KEY_MAP = {
    "control": "ctrl",
    "command": "cmd",
    "meta": "cmd"
}

SLEEP_ACTION = 0.1
SLEEP_SCREENSHOT = 0.5
SLEEP_NAVIGATION = 1.0

class DaytonaComputer(Computer):
    """Connects to a Daytona sandbox for computer use operations."""

    def __init__(
        self,
        screen_size: tuple[int, int],
        initial_url: str = "https://www.duckduckgo.com/",
        search_engine_url: str = "https://duckduckgo.com/",
        network_block_all: bool = False,
        network_allow_list: Optional[str] = "0.0.0.0/0",
        auto_stop_interval: int = 30,
    ):
        self._screen_size = screen_size
        self._initial_url = initial_url
        self._search_engine_url = search_engine_url
        self._network_block_all = network_block_all
        self._network_allow_list = network_allow_list
        self._auto_stop_interval = auto_stop_interval

        self._daytona = None
        self._sandbox = None
        self._current_url = initial_url

    def __enter__(self):

        # Initialize Daytona client
        daytona_config = DaytonaConfig(
            api_key=os.environ.get("DAYTONA_API_KEY", ""),
        )
        self._daytona = Daytona(daytona_config)

        # Create sandbox
        try:
            params = CreateSandboxFromSnapshotParams(
                network_block_all=self._network_block_all,
                network_allow_list=self._network_allow_list,
                auto_stop_interval=self._auto_stop_interval,
            )

            self._sandbox = self._daytona.create(params)

            self._sandbox.computer_use.start()

            termcolor.cprint(
                f"Daytona sandbox started: {self._sandbox.id}",
                color="green",
                attrs=["bold"],
            )

        except DaytonaError as e:
            termcolor.cprint(f"Failed to create sandbox: {e}", color="red")
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._sandbox:
            try:
                self._sandbox.delete()
            except Exception as e:
                termcolor.cprint(f"Sandbox cleanup failed: {e}", color="red")

    def screen_size(self) -> tuple[int, int]:
        return self._screen_size

    def open_web_browser(self) -> EnvState:
        """Opens the web browser by navigating to the initial URL."""

        cmd = f"sh -c 'DISPLAY=:0 xdg-open \"{self._initial_url}\" > /dev/null 2>&1 &'"

        self._sandbox.process.exec(cmd, timeout=1)

        time.sleep(SLEEP_NAVIGATION)
        self._current_url = self._initial_url

        return self.current_state()

    def click_at(self, x: int, y: int) -> EnvState:
        self._sandbox.computer_use.mouse.click(x, y, "left")
        time.sleep(SLEEP_ACTION)
        return self.current_state()

    def hover_at(self, x: int, y: int) -> EnvState:
        self._sandbox.computer_use.mouse.move(x, y)
        time.sleep(SLEEP_ACTION)
        return self.current_state()

    def type_text_at(
        self,
        x: int,
        y: int,
        text: str,
        press_enter: bool = False,
        clear_before_typing: bool = True,
    ) -> EnvState:
        self._sandbox.computer_use.mouse.click(x, y, "left")
        time.sleep(SLEEP_ACTION)

        if clear_before_typing:
            self._sandbox.computer_use.keyboard.press("ctrl+a")
            time.sleep(SLEEP_ACTION)

        self._sandbox.computer_use.keyboard.type(text, delay=50)

        if press_enter:
            self._sandbox.computer_use.keyboard.press("enter")
            time.sleep(SLEEP_NAVIGATION)
        else:
            time.sleep(SLEEP_ACTION)

        return self.current_state()

    def scroll_document(
        self, direction: Literal["up", "down", "left", "right"]
    ) -> EnvState:
        if direction == "down":
            self._sandbox.computer_use.keyboard.press("pagedown")
        elif direction == "up":
            self._sandbox.computer_use.keyboard.press("pageup")
        elif direction in ("left", "right"):
            scroll_amount = self._screen_size[0] // 2
            center_x = self._screen_size[0] // 2
            center_y = self._screen_size[1] // 2
            return self.scroll_at(center_x, center_y, direction, scroll_amount)
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        time.sleep(SLEEP_ACTION)
        return self.current_state()

    def scroll_at(
        self,
        x: int,
        y: int,
        direction: Literal["up", "down", "left", "right"],
        magnitude: int = 800,
    ) -> EnvState:

        self._sandbox.computer_use.mouse.click(x, y)
        time.sleep(SLEEP_ACTION)

        if direction == "down":
            #Currently computer_use.mouse.scroll times out
            #self._sandbox.computer_use.mouse.scroll(x,y,"down", amount)
            self._sandbox.computer_use.keyboard.press("pagedown")
        elif direction == "up":
            #self._sandbox.computer_use.mouse.scroll(x,y,"up", amount)
            self._sandbox.computer_use.keyboard.press("pageup")
        elif direction == "right":
            self._sandbox.computer_use.keyboard.press("space")
        elif direction == "left":
            self._sandbox.computer_use.keyboard.hotkey("shift+space")
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        time.sleep(SLEEP_ACTION)
        return self.current_state()

    def wait_5_seconds(self) -> EnvState:
        time.sleep(5)
        return self.current_state()

    def go_back(self) -> EnvState:
        self._sandbox.computer_use.keyboard.hotkey("alt+left")
        time.sleep(SLEEP_NAVIGATION)
        return self.current_state()

    def go_forward(self) -> EnvState:
        self._sandbox.computer_use.keyboard.hotkey("alt+right")
        time.sleep(SLEEP_NAVIGATION)
        return self.current_state()

    def search(self) -> EnvState:
        return self.navigate(self._search_engine_url)

    def navigate(self, url: str) -> EnvState:
        normalized_url = url
        if not normalized_url.startswith(("http://", "https://")):
            normalized_url = "https://" + normalized_url

        self._current_url = normalized_url

        self._sandbox.computer_use.keyboard.press("f6")
        time.sleep(SLEEP_ACTION)

        self._sandbox.computer_use.keyboard.type(normalized_url)
        time.sleep(SLEEP_ACTION)

        self._sandbox.computer_use.keyboard.press("enter")
        time.sleep(SLEEP_NAVIGATION)

        return self.current_state()

    def key_combination(self, keys: list[str]) -> EnvState:
        normalized_keys = [DAYTONA_KEY_MAP.get(k.lower(), k) for k in keys]

        if len(normalized_keys) == 1:
            self._sandbox.computer_use.keyboard.press(normalized_keys[0])
            time.sleep(SLEEP_ACTION)
            return self.current_state()

        hotkey_str = "+".join(normalized_keys)

        self._sandbox.computer_use.keyboard.hotkey(hotkey_str)
        time.sleep(SLEEP_ACTION)

        return self.current_state()

    def drag_and_drop(
        self, x: int, y: int, destination_x: int, destination_y: int
    ) -> EnvState:
        self._sandbox.computer_use.mouse.drag(x, y, destination_x, destination_y)
        time.sleep(SLEEP_ACTION)
        return self.current_state()

    def current_state(self) -> EnvState:
        time.sleep(SLEEP_SCREENSHOT)
        try:
            screenshot = self._sandbox.computer_use.screenshot.take_compressed(
                ScreenshotOptions(fmt="png", show_cursor=True)
            )
            screenshot_bytes = base64.b64decode(screenshot.screenshot)
        except Exception as e:
            termcolor.cprint(f"Screenshot failed: {e}", color="red")
            raise
        
        return EnvState(screenshot=screenshot_bytes, url=self._current_url)