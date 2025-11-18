import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pygame.pkgdata')

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import time
import threading
import tkinter as tk
import random

import pygame
pygame.mixer.init()

from PIL import Image, ImageTk, ImageDraw, ImageFont
from src.track_nearby_buses import track_nearby_buses


BUS_IMAGE_PATH = os.path.join('assets', 'images', 'bus')
EXPLOSION_IMAGE_PATH = lambda frame: os.path.join('assets', 'images', 'explosion', f'explosion_{frame}.png')
BUS_SIGN_FONT_PATH = os.path.join('assets', 'fonts', 'vhs-gothic.ttf')
BUS_ENGINE_SOUND_PATH = os.path.join('assets', 'sounds', 'engine.wav')
BUS_BEEP_SOUND_PATH = os.path.join('assets', 'sounds', 'beep3.wav')
EXPLOSION_SOUND_PATH = os.path.join('assets', 'sounds', 'explosion.wav')

BUS_ROUTE_COLORS = {
    'small': [
        '68'
    ],
    'grey': [
        '33', '49', '4', '14', '84'
    ],
    'blue': [
        '25', '44', '99'
    ],
    'green': [
        'R4'
    ]
}
BUS_SIGN_FONTSIZE = 10
BUS_SIGN_COLOR = (255, 165, 0, 255)
BUS_SIGN_PIXEL_OFFSETS = {
    'small': (54, 20),
    'grey': (154, 20),
    'blue': (154, 28),
    'green': (154, 28)
}

BUS_SPEED_PIXELS_PER_S = 200
BUS_BOUNCE_INTERVAL_PIXELS = 80
BUS_BOUNCE_SIGN_OFFSET_PIXELS = 4
BUS_JUMP_VELOCITY_PIXELS_PER_S = lambda: random.uniform(-500, -250)
BUS_GRAVITY_PIXELS_PER_S2 = 2000
BUS_HEAT_PER_CLICK = 0.1
BUS_COOLDOWN_PER_S = 0.1
EXPLOSION_ANIMATION_FRAME_DURATION_S = 0.05
EXPLOSION_OFFSET = (0, -96)


class RenderState:

    class RenderedBus:

        def __init__(self, parent, bus_data):
            self.parent = parent
            self.bus_data = bus_data
            self.active = True

            self.bus_color = 'grey'
            for color in BUS_ROUTE_COLORS:
                if bus_data['route_name'] in BUS_ROUTE_COLORS[color]:
                    self.bus_color = color
                    break

            self.bus_img_up = ImageTk.PhotoImage(Image.open(os.path.join(BUS_IMAGE_PATH, f'bus_{self.bus_color}_up.png')))
            self.bus_img_down = ImageTk.PhotoImage(Image.open(os.path.join(BUS_IMAGE_PATH, f'bus_{self.bus_color}_down.png')))
            self.explosion_offset = ( (self.bus_img_up.width() - parent.explosion_size[0]) // 2,
                                      (self.bus_img_up.height() - parent.explosion_size[1]) // 2 )

            self.x = -self.bus_img_up.width()
            self.y = self.parent.canvas_shape[1] - self.bus_img_up.height()
            self.velocity_y = 0
            self.heat = 0
            self.exploded = False
            self.explosion_animation_time = 0

            self.text_img = create_text_image(
                text=bus_data['route_name'],
                font_path=BUS_SIGN_FONT_PATH,
                font_size=BUS_SIGN_FONTSIZE,
                color=BUS_SIGN_COLOR
            )

        def handle_click(self):
            self.velocity_y = BUS_JUMP_VELOCITY_PIXELS_PER_S()
            self.heat = self.heat + BUS_HEAT_PER_CLICK

        def update(self, dt_s: float):
            if self.exploded:
                self.explosion_animation_time += dt_s
            else:
                self.heat = max(0, self.heat - dt_s * BUS_COOLDOWN_PER_S)
                if self.heat >= 1:
                    self.exploded = True
                    self.active = False
                    self.parent.explosion_sound.play()
                else:
                    self.x += BUS_SPEED_PIXELS_PER_S * dt_s
                    self.velocity_y += BUS_GRAVITY_PIXELS_PER_S2 * dt_s
                    self.y += self.velocity_y * dt_s

                    if self.y > self.parent.canvas_shape[1] - self.bus_img_up.height():
                        self.y = self.parent.canvas_shape[1] - self.bus_img_up.height()
                        self.velocity_y = 0
                    if self.x > self.parent.canvas_shape[0]:
                        self.active = False

        def render(self):
            if self.active:
                is_up = self.x % BUS_BOUNCE_INTERVAL_PIXELS < (BUS_BOUNCE_INTERVAL_PIXELS / 2)
                self.parent.canvas.create_image(self.x, self.y, anchor="nw", image=self.bus_img_up if is_up else self.bus_img_down)
                self.parent.canvas.create_image(self.x + BUS_SIGN_PIXEL_OFFSETS[self.bus_color][0], self.y + BUS_SIGN_PIXEL_OFFSETS[self.bus_color][1] - (BUS_BOUNCE_SIGN_OFFSET_PIXELS if is_up else 0), anchor="nw", image=self.text_img)
                return True
            
            if self.exploded:
                frame = int(self.explosion_animation_time / EXPLOSION_ANIMATION_FRAME_DURATION_S)
                if frame < len(self.parent.explosion_images):
                    self.parent.canvas.create_image(self.x + self.explosion_offset[0] + EXPLOSION_OFFSET[0], self.y + self.explosion_offset[1] + EXPLOSION_OFFSET[1], anchor="nw", image=self.parent.explosion_images[frame])
            
            return False

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.canvas_shape = (canvas.winfo_screenwidth(), canvas.winfo_screenheight())

        self.buses = []
        self.bus_lock = threading.RLock()
        self.bus_index = 0
        self.bus_interval = lambda: random.uniform(1.5, 2.5)
        self.bus_interval_timer = 0

        self.explosion_images = [
            ImageTk.PhotoImage(Image.open(os.path.join(EXPLOSION_IMAGE_PATH(i)))) for i in range(0, 17)
        ]
        self.explosion_size = (self.explosion_images[0].width(), self.explosion_images[0].height())
        self.explosion_sound = pygame.mixer.Sound(EXPLOSION_SOUND_PATH)
        self.explosion_sound.set_volume(0.5)

        self.rendered_buses = []
        self.previous_advance_time = None

        self.engine_sound = pygame.mixer.Sound(BUS_ENGINE_SOUND_PATH)
        self.engine_channel = self.engine_sound.play(loops=-1)
        self.engine_channel.set_volume(0)

    def advance(self):
        if self.previous_advance_time is None:
            self.previous_advance_time = time.perf_counter()
            return
        current_time = time.perf_counter()
        dt_s = current_time - self.previous_advance_time

        self.bus_interval_timer = max(0, self.bus_interval_timer - dt_s)
        if self.bus_interval_timer == 0:
            with self.bus_lock:
                if len(self.buses) > self.bus_index:
                    self.rendered_buses.append(self.RenderedBus(self, self.buses[self.bus_index]))
                    self.bus_index += 1
                    self.bus_interval_timer = self.bus_interval()
                else:
                    self.bus_interval_timer = 0.5
        
        for bus in self.rendered_buses:
            bus.update(dt_s)
        
        self.previous_advance_time = current_time

    def render(self):
        self.canvas.delete('all')
        any_rendered = False
        for bus in self.rendered_buses:
            if bus.render():
                any_rendered = True
        if any_rendered:
            self.engine_channel.set_volume(min(0.25, self.engine_channel.get_volume() + 0.01))
        else:
            self.engine_channel.set_volume(max(0, self.engine_channel.get_volume() - 0.0005))

    def handle_click(self, click_position):
        for bus in self.rendered_buses:
            if bus.x <= click_position[0] <= bus.x + bus.bus_img_up.width() and \
               bus.y <= click_position[1] <= bus.y + bus.bus_img_up.height():
                bus.handle_click()


def create_text_image(text: str, font_path: str, font_size: int, color: tuple):
    font = ImageFont.truetype(font_path, font_size)
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), text, font=font, fill=color)

    return ImageTk.PhotoImage(img)


def update_tk(root: tk.Tk, canvas: tk.Canvas, state: RenderState):
    state.advance()
    state.render()
    root.after(10, update_tk, root, canvas, state)


def handle_click_tk(state: RenderState):
    click_position = (state.canvas.winfo_pointerx(), state.canvas.winfo_pointery())

    state.handle_click(click_position)

    sound = pygame.mixer.Sound(BUS_BEEP_SOUND_PATH)
    sound.set_volume(0.3)
    sound.play()


if __name__ == '__main__':
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.attributes('-transparentcolor', 'white')
    root.overrideredirect(True)
    
    canvas = tk.Canvas(root, width=root.winfo_screenwidth(), height=root.winfo_screenheight(), bg='white', highlightthickness=0)
    canvas.pack()

    state = RenderState(canvas)

    root.bind('<Escape>', lambda _: root.destroy())
    root.bind('<Button-1>', lambda _: handle_click_tk(state))

    tracking_thread = threading.Thread(target=track_nearby_buses, args=(state.buses, state.bus_lock), daemon=True)
    tracking_thread.start()

    update_tk(root, canvas, state)

    root.mainloop()