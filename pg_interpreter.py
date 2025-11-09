# pg_interpreter.py - FULLY FIXED + EMBEDDED PREVIEW MODE (copy-paste this entire file)

import pygame
import sys
import re
import time
import os
import tkinter as tk
import traceback

COLORS = {
    'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255), 'brown': (139, 69, 19),
    'gold': (255, 215, 0), 'gray': (128, 128, 128), 'skyblue': (135, 206, 235), 'black': (0, 0, 0),
    'yellow': (255, 255, 0), 'orange': (255, 165, 0), 'purple': (128, 0, 128),
    'darkgreen': (0, 100, 0), 'navy': (0, 0, 128), 'pink': (255, 192, 203)
}

KEY_MAP = {
    'left': pygame.K_LEFT, 'right': pygame.K_RIGHT, 'up': pygame.K_UP, 'down': pygame.K_DOWN,
    'space': pygame.K_SPACE, 'a': pygame.K_a, 'd': pygame.K_d, 'w': pygame.K_w, 's': pygame.K_s, 'p': pygame.K_p
}

class PGGame:
    def __init__(self, width=800, height=600, world_width=2500, fps=60, title="PixelGame", embedded=False, tk_root=None):
        self.embedded = embedded
        self.tk_root = tk_root
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.world_width = world_width
        self.sprites = {}
        self.platforms = []
        self.gravity = 0.5
        self.jump_power = -12.0
        self.bg_color = COLORS['skyblue']
        self.camera_x = 0
        self.message = None
        self.paused_until = 0
        self.running = True
        self.eye_sprites = set()
        self.font = pygame.font.Font(None, 74)
        self.small_font = pygame.font.Font(None, 48)

    def parse_color(self, c):
        c = c.lower().strip().replace('#', '')
        if ',' in c:
            return tuple(int(x.strip()) for x in c.split(','))
        if len(c) == 6 and all(ch in '0123456789abcdef' for ch in c):
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        return COLORS.get(c, (255, 100, 100))

    def create_sprite(self, name, x, y, w, h, color):
        col = self.parse_color(color)
        s = {
            'rect': pygame.Rect(x, y, w, h),
            'vx': 0.0, 'vy': 0.0,
            'color': col,
            'jump_power': self.jump_power,
            'gravity': True,
            'remove': False
        }
        s['gravity'] = 'player' in name.lower() or 'mario' in name.lower() or 'bird' in name.lower() or 'goomba' in name.lower() or 'enemy' in name.lower()
        self.sprites[name] = s
        if 'coin' in name.lower():
            s['gravity'] = False
            s['collectable'] = True
        if 'goomba' in name.lower() or 'enemy' in name.lower():
            s['enemy'] = True

    def create_platform(self, x, y, w, h, color):
        col = self.parse_color(color)
        self.platforms.append({'rect': pygame.Rect(x, y, w, h), 'color': col})

    def jump(self, name):
        s = self.sprites[name]
        if s['vy'] >= 0:
            s['vy'] = self.jump_power

    def move_dir(self, name, dirr, speed):
        s = self.sprites[name]
        if dirr == 'right':
            s['vx'] = speed
        elif dirr == 'left':
            s['vx'] = -speed
        elif dirr == 'up':
            s['vy'] = -speed
        elif dirr == 'down':
            s['vy'] = speed

    def stop(self, name):
        self.sprites[name]['vx'] = 0

    def set_message(self, msg, x, y, size, color):
        self.message = (msg, x, y, size, color)

    def horizontal_collisions(self, rect, name):
        s = self.sprites[name]
        for p in self.platforms:
            if rect.colliderect(p['rect']):
                if s['vx'] > 0:
                    rect.right = p['rect'].left
                elif s['vx'] < 0:
                    rect.left = p['rect'].right

    def vertical_collisions(self, rect, name):
        s = self.sprites[name]
        on_ground = False
        for p in self.platforms:
            if rect.colliderect(p['rect']):
                if s['vy'] > 0:
                    rect.bottom = p['rect'].top
                    on_ground = True
                    s['vy'] = 0
                elif s['vy'] < 0:
                    rect.top = p['rect'].bottom
                    s['vy'] = 0
        return on_ground

    def update_physics(self):
        for name, s in list(self.sprites.items()):
            if s['remove']:
                del self.sprites[name]
                continue
            r = s['rect']
            if s['gravity']:
                s['vy'] += self.gravity
            r.x += s['vx']
            self.horizontal_collisions(r, name)
            r.y += s['vy']
            self.vertical_collisions(r, name)
            s['rect'] = r

            player_rect = self.sprites.get('player', {}).get('rect') or self.sprites.get('mario', {}).get('rect') or self.sprites.get('bird', {}).get('rect', pygame.Rect(0,0,0,0))
            if player_rect and r.colliderect(player_rect) and name not in ('player', 'mario', 'bird'):
                if s.get('collectable'):
                    s['remove'] = True
                elif s.get('enemy'):
                    self.set_message("GAME OVER!", 250, 250, 100, (255, 0, 0))
                    self.paused_until = pygame.time.get_ticks() + 3000
                    self.running = False

    def update_camera(self):
        pname = next((n for n in self.sprites if n in ('player', 'mario', 'bird')), None)
        if pname:
            px = self.sprites[pname]['rect'].centerx
            target = px - self.screen.get_width() // 2
            self.camera_x = max(0, min(target, self.world_width - self.screen.get_width()))

    def exec_cmd(self, keys, line):
        for sub_line in line.split(';'):
            sub_line = sub_line.strip()
            if not sub_line: continue
            words = sub_line.split()
            cmd = words[0].lower()
            if cmd == 'create':
                pos_match = re.search(r'at\s+([\d\.]+)\s*,\s*([\d\.]+)', sub_line)
                if pos_match:
                    x = float(pos_match.group(1))
                    y = float(pos_match.group(2))
                else:
                    continue
                name = words[1]
                w = h = 40
                color = 'red'
                is_plat = name == 'platform'
                size_match = re.search(r'size\s+([\d\.]+)', sub_line)
                if size_match:
                    w = h = float(size_match.group(1))
                width_match = re.search(r'width\s+([\d\.]+)', sub_line)
                height_match = re.search(r'height\s+([\d\.]+)', sub_line)
                if width_match:
                    w = float(width_match.group(1))
                if height_match:
                    h = float(height_match.group(1))
                color_match = re.search(r'color\s+([\w#]+)', sub_line)
                if color_match:
                    color = color_match.group(1)
                if is_plat:
                    self.create_platform(x, y, w, h, color)
                else:
                    self.create_sprite(name, x, y, w, h, color)
            elif cmd == 'background':
                self.bg_color = self.parse_color(' '.join(words[1:]))
            elif cmd == 'gravity':
                self.gravity = 0.5 if words[1] == 'on' else 0.0
            elif cmd == 'jump' and len(words) == 3 and words[1] == 'power':
                self.jump_power = -float(words[2])
            elif cmd == 'move':
                dirr = words[1]
                name = words[2]
                speed = 5.0
                if len(words) > 3 and words[3] == 'speed':
                    speed = float(words[4])
                self.move_dir(name, dirr, speed)
            elif cmd == 'stop':
                self.stop(words[1])
            elif cmd == 'jump':
                self.jump(words[1])
            elif cmd == 'text':
                q1 = sub_line.find('"')
                q2 = sub_line.find('"', q1 + 1)
                if q1 != -1 and q2 != -1:
                    msg = sub_line[q1 + 1:q2]
                    rest = sub_line[q2 + 1:].strip()
                    at_i = rest.lower().find('at ')
                    if at_i != -1:
                        pos_s = rest[at_i + 3:].strip()
                        x, y = map(float, pos_s.split(',')[:2])
                        size = 74
                        col = (255, 0, 0)
                        self.set_message(msg, x, y, size, col)
            elif cmd == 'wait':
                secs = float(words[1])
                self.paused_until = pygame.time.get_ticks() + int(secs * 1000)
            elif cmd == 'quit':
                self.running = False
            elif cmd == 'draw' and words[1] == 'eyes' and words[2] == 'on':
                self.eye_sprites.add(words[3])
            elif cmd == 'set':
                prop = words[1]
                name = words[2]
                value = float(words[-1])
                r = self.sprites[name]['rect']
                if prop == 'x':
                    r.x = value
                elif prop == 'y':
                    r.y = value
            elif cmd == 'reverse':
                prop = words[1]
                name = words[2]
                s = self.sprites[name]
                if prop == 'x':
                    s['vx'] = -s['vx']
                elif prop == 'y':
                    s['vy'] = -s['vy']

    def eval_cond(self, keys, cond):
        cond = cond.strip().lower()
        if cond.startswith('not '):
            return not self.eval_cond(keys, cond[4:])
        if ' or ' in cond:
            for part in cond.split(' or '):
                if self.eval_cond(keys, part.strip()):
                    return True
            return False
        if cond.startswith('key '):
            kname = cond[4:].strip()
            return keys[KEY_MAP.get(kname, 0)]
        if ' touches ' in cond:
            parts = cond.split(' touches ')
            if len(parts) == 2:
                s1 = parts[0].strip()
                s2 = parts[1].strip()
                r1 = self.sprites.get(s1, {}).get('rect', pygame.Rect(0,0,0,0))
                r2 = self.sprites.get(s2, {}).get('rect', pygame.Rect(0,0,0,0))
                return r1.colliderect(r2)
        match = re.match(r'^(\w+)\s+(x|y)\s+([><=])\s+(\d+(?:\.\d+)?)$', cond)
        if match:
            sname, prop, op, valstr = match.groups()
            val = float(valstr)
            s = self.sprites.get(sname, {})
            r = s.get('rect', pygame.Rect(0,0,0,0))
            pos = r.x if prop == 'x' else r.y
            if op == '>': return pos > val
            if op == '<': return pos < val
            if op == '=': return pos == val
        return False

    def exec_block(self, block, keys):
        for stmt in block:
            if stmt['type'] == 'cmd':
                self.exec_cmd(keys, stmt['line'])
            elif stmt['type'] == 'if':
                if self.eval_cond(keys, stmt['cond']):
                    self.exec_block(stmt['block'], keys)

    def parse_program(self, lines):
        i = 0
        init_block = []
        frame_block = []
        block_stack = [init_block]
        indent_stack = [0]
        current_block = init_block
        while i < len(lines):
            raw_line = lines[i]
            line = raw_line.strip()
            if not line or line.startswith('#'):
                i += 1
                continue
            indent = len(raw_line) - len(raw_line.lstrip())
            while indent < indent_stack[-1]:
                indent_stack.pop()
                block_stack.pop()
            current_block = block_stack[-1]
            if indent > indent_stack[-1]:
                indent_stack.append(indent)
            if line == 'every frame:':
                current_block = frame_block
                block_stack = [frame_block]
                indent_stack = [indent]
                i += 1
                continue
            if line.endswith(':') and line.startswith('if '):
                cond = line[3:-1].strip()
                sub_block = []
                current_block.append({'type': 'if', 'cond': cond, 'block': sub_block})
                block_stack.append(sub_block)
                i += 1
                continue
            current_block.append({'type': 'cmd', 'line': line})
            i += 1
        return init_block, frame_block

    def run_block(self, block, keys={}):
        self.exec_block(block, keys)

    def draw(self):
        self.screen.fill(self.bg_color)
        cam_x = self.camera_x
        for p in self.platforms:
            px = p['rect'].x - cam_x
            if px + p['rect'].width > 0 and px < self.screen.get_width():
                pygame.draw.rect(self.screen, p['color'], (int(px), int(p['rect'].y), int(p['rect'].width), int(p['rect'].height)))
        for name, s in self.sprites.items():
            if s['remove']: continue
            px = s['rect'].x - cam_x
            if px + s['rect'].width > 0 and px < self.screen.get_width():
                pygame.draw.rect(self.screen, s['color'], (int(px), int(s['rect'].y), int(s['rect'].width), int(s['rect'].height)))
                if name in self.eye_sprites:
                    ex1 = s['rect'].centerx - 8 - cam_x
                    ey1 = s['rect'].centery - 5
                    ex2 = s['rect'].centerx + 8 - cam_x
                    pygame.draw.circle(self.screen, (0,0,0), (int(ex1), int(ey1)), 4)
                    pygame.draw.circle(self.screen, (0,0,0), (int(ex2), int(ey1)), 4)
        if self.message:
            msg, mx, my, msize, mcol = self.message
            font = self.font if msize > 60 else self.small_font
            text_surf = font.render(msg, True, mcol)
            self.screen.blit(text_surf, (mx, my))
        pygame.display.flip()

    def run(self, filename):
        with open(filename, 'r') as f:
            lines = f.readlines()

        init_block, frame_block = self.parse_program(lines)

        if 'mario' in self.sprites:
            self.sprites['player'] = self.sprites['mario']

        try:
            self.run_block(init_block)
        except Exception:
            print(traceback.format_exc())
            self.running = False

        self.running = True
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            keys = pygame.key.get_pressed()
            now = pygame.time.get_ticks()

            if self.paused_until > now:
                self.draw()
                self.clock.tick(self.fps)
                if self.embedded:
                    self.tk_root.update()
                continue

            try:
                self.run_block(frame_block, keys)
                self.update_physics()
                self.update_camera()
            except Exception:
                print(traceback.format_exc())
                self.running = False

            self.draw()
            self.clock.tick(self.fps)
            if self.embedded:
                self.tk_root.update()

        if not self.embedded:
            pygame.quit()
            sys.exit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pg_interpreter.py yourgame.pg")
        sys.exit(1)
    filename = sys.argv[1]
    if not os.path.exists(filename):
        print(f"File {filename} not found!")
        sys.exit(1)
    title = os.path.splitext(os.path.basename(filename))[0].replace('_', ' ').title()
    game = PGGame(title=title)
    game.run(filename)