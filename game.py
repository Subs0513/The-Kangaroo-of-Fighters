# -*- coding: utf-8 -*-
"""
无擂台版本：对战逻辑 + UI（血条/头像/姓名）
变更点：
1) 删除了矩形擂台的绘制与边界，改为基于屏幕边缘做活动边界
2) 角色默认放大（支持在 players[i].scale 或 players[i].size 中配置）
"""
import pygame as pg
from typing import Dict, Any, Optional

# ---------------- 工具 ----------------
def load_image_optional(path: str, size=None):
    if not path:
        return None
    try:
        img = pg.image.load(path).convert_alpha()
        if size:
            img = pg.transform.smoothscale(img, size)
        return img
    except Exception as e:
        print(f"[asset] 载入失败 {path}: {e}")
        return None

def key_from_name(name: str) -> int:
    name = name.lower()
    name_map = {"left": pg.K_LEFT, "right": pg.K_RIGHT, "up": pg.K_UP, "down": pg.K_DOWN,
                "space": pg.K_SPACE, "enter": pg.K_RETURN, "esc": pg.K_ESCAPE}
    if name in name_map:
        return name_map[name]
    if len(name) == 1 and "a" <= name <= "z":
        return getattr(pg, f"K_{name}")
    if len(name) == 1 and "0" <= name <= "9":
        return getattr(pg, f"K_{name}")
    return pg.K_SPACE

# ---------------- 角色 ----------------
class Fighter:
    def __init__(self, cfg: Dict[str, Any], world, override_sprite: Optional[str] = None):
        self.world = world
        self.display_name = cfg.get("display_name", "player")

        # === 放大逻辑 ===
        # 优先读取 size（像素），否则使用默认 80x120；再用 scale 进行整体缩放（默认 1.35）
        base_w, base_h = cfg.get("size", [80, 120])
        scale = float(cfg.get("scale", 1.35))
        self.w, self.h = int(base_w * scale), int(base_h * scale)

        self.color = tuple(cfg.get("color", [255, 255, 255]))

        # 贴图（可被 main 的角色选择覆盖；否则走 config 默认）
        self.sprite_path = override_sprite if override_sprite else cfg.get("sprite_image", "")
        self.sprite = load_image_optional(self.sprite_path, (self.w, self.h))
        self.avatar_raw = load_image_optional(self.sprite_path, None)

        start_x = int(cfg.get("start_x", 100))
        self.facing_right = bool(cfg.get("facing_right", True))
        self.rect = pg.Rect(start_x, world.ground_y - self.h, self.w, self.h)

        self.hp = self.max_hp = int(cfg.get("hp", 100))
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.state = "idle"
        self.attack_timer = 0
        self.hitstop = 0

        self.keys = {k: key_from_name(v) for k, v in cfg.get("keys", {}).items()}

    def input(self, keys):
        # 处于硬直时不接受输入，但会在 physics 中被动位移
        if self.hitstop > 0:
            return
        self.vx = 0.0
        if keys[self.keys.get("L")]:
            self.vx = -self.world.move_speed
            self.facing_right = False
        if keys[self.keys.get("R")]:
            self.vx = self.world.move_speed
            self.facing_right = True
        if keys[self.keys.get("JUMP")] and self.on_ground:
            self.vy = self.world.jump_v
            self.on_ground = False
        if keys[self.keys.get("ATK")] and self.attack_timer <= 0:
            self.state = "attack"
            self.attack_timer = self.world.attack_total

    def physics(self):
        bounds = self.world.bounds_rect  # (x, y, w, h)

        # 无论是否硬直，都允许击退速度推动角色，并逐帧衰减
        if self.hitstop > 0:
            self.rect.x += int(self.vx)
            self.vx *= 0.85
            if abs(self.vx) < 0.05:
                self.vx = 0.0
            # 贴边限制（基于屏幕）
            bx, by, bw, bh = bounds
            self.rect.x = max(bx, min(self.rect.x, bx + bw - self.w))
            self.hitstop -= 1
            return

        # 水平位移 + 摩擦衰减
        self.rect.x += int(self.vx)
        self.vx *= 0.85
        if abs(self.vx) < 0.05:
            self.vx = 0.0

        # 屏幕边界限制
        bx, by, bw, bh = bounds
        self.rect.x = max(bx, min(self.rect.x, bx + bw - self.w))

        # 垂直重力
        if not self.on_ground:
            self.vy += self.world.gravity
            self.rect.y += int(self.vy)
            if self.rect.bottom >= self.world.ground_y:
                self.rect.bottom = self.world.ground_y
                self.vy = 0.0
                self.on_ground = True

        # 攻击帧计时
        if self.attack_timer > 0:
            self.attack_timer -= 1
            if self.attack_timer == 0:
                self.state = "idle"

    def attack_hitbox(self):
        if self.state != "attack":
            return None
        elapsed = self.world.attack_total - self.attack_timer
        if self.world.startup < elapsed <= self.world.startup + self.world.active:
            w, h = self.world.hb_w, self.world.hb_h
            y_off = self.world.hb_y
            if self.facing_right:
                return pg.Rect(self.rect.right, self.rect.y + y_off, w, h)
            else:
                return pg.Rect(self.rect.left - w, self.rect.y + y_off, w, h)
        return None

    def get_hurt(self, dmg, kb, from_right: bool):
        # 扣血 + 击退 + 硬直（硬直期间仍会被动后退）
        if self.hitstop > 0:
            return
        self.hp = max(0, self.hp - int(dmg))
        self.vx = (-kb if from_right else kb)
        self.hitstop = self.world.hitstop

    def draw(self, screen):
        if self.sprite:
            img = self.sprite if self.facing_right else pg.transform.flip(self.sprite, True, False)
            screen.blit(img, self.rect.topleft)
        else:
            pg.draw.rect(screen, self.color, self.rect, border_radius=6)
            # 简易“脸点”，仅在无贴图时区分朝向
            nose_x = self.rect.centerx + (15 if self.facing_right else -15)
            pg.draw.circle(screen, (0, 0, 0), (nose_x, self.rect.centery - 10), 4)

# ---------------- 世界/舞台 ----------------
class World:
    def __init__(self, cfg: Dict[str, Any]):
        self.W, self.H = cfg["window"]["width"], cfg["window"]["height"]

        p = cfg["physics"]
        self.gravity = p["gravity"]
        self.jump_v = p["jump_v"]
        self.move_speed = p["move_speed"]
        self.hitstop = p["hitstop"]
        self.FPS = p.get("fps", 60)

        atk = cfg["attack"]
        self.startup = atk["startup"]
        self.active = atk["active"]
        self.recovery = atk["recovery"]
        self.attack_total = self.startup + self.active + self.recovery
        self.damage = atk["damage"]
        self.kb = atk["knockback"]
        hb = atk["hitbox"]
        self.hb_w = hb["w"]
        self.hb_h = hb["h"]
        self.hb_y = hb["y_offset"]

        stage = cfg["stage"]
        self.bg_color = tuple(stage.get("background_color", [240, 240, 240]))
        self.bg_image = load_image_optional(stage.get("background_image", ""), (self.W, self.H))

        # === 无擂台：仅使用屏幕边界作为活动范围 ===
        margin = int(stage.get("screen_margin", 12))  # 给边缘留点缓冲
        self.bounds_rect = (margin, margin, self.W - margin * 2, self.H - margin * 2)

        # 地面高度（角色脚落地线），默认在底部往上 80 像素，也可在 config.stage.ground_y 调整
        self.ground_y = int(stage.get("ground_y", self.H - 80))

        ui = cfg.get("ui", {})
        self.font = pg.font.SysFont("Microsoft YaHei", 32)
        self.font_small = pg.font.SysFont("Microsoft YaHei", int(ui.get("font_small_size", 24)))
        self.left_margin = int(ui.get("left_margin", 40))
        self.top_margin = int(ui.get("top_margin", 24))
        self.bar_w = int(ui.get("bar_w", 360))
        self.bar_h = int(ui.get("bar_h", 18))
        self.name_avatar_gap = int(ui.get("name_avatar_gap", 8))
        self.name_bar_gap = int(ui.get("name_bar_gap", 6))

    def draw_stage(self, screen):
        if self.bg_image:
            screen.blit(self.bg_image, (0, 0))
        else:
            screen.fill(self.bg_color)
        # 无擂台：不再绘制任何矩形地面/边框

    def _draw_hp_bar(self, screen, x, y, w, h, hp, maxhp):
        ratio = max(0.0, float(hp) / maxhp)
        pg.draw.rect(screen, (60, 60, 60), (x, y, w, h), border_radius=4)
        pg.draw.rect(screen, (220, 60, 60), (x, y, int(w * ratio), h), border_radius=4)
        pg.draw.rect(screen, (0, 0, 0), (x, y, w, h), 2, border_radius=4)

    def draw_ui(self, screen, p1: Fighter, p2: Fighter, winner):
        left_x = self.left_margin
        right_x = screen.get_width() - self.left_margin - self.bar_w
        bar_y = self.top_margin + self.font_small.get_height() + self.name_bar_gap

        # 左侧
        name1 = self.font_small.render(p1.display_name, True, (0, 0, 0))
        th = name1.get_height()
        av1 = pg.transform.smoothscale(p1.avatar_raw, (th, th)) if p1.avatar_raw else None
        if av1:
            screen.blit(av1, (left_x, self.top_margin))
        else:
            pg.draw.rect(screen, p1.color, (left_x, self.top_margin, th, th), border_radius=6)
        screen.blit(name1, (left_x + th + self.name_avatar_gap, self.top_margin))
        self._draw_hp_bar(screen, left_x, bar_y, self.bar_w, self.bar_h, p1.hp, p1.max_hp)

        # 右侧
        name2 = self.font_small.render(p2.display_name, True, (0, 0, 0))
        th2 = name2.get_height()
        av2 = pg.transform.smoothscale(p2.avatar_raw, (th2, th2)) if p2.avatar_raw else None
        if av2:
            screen.blit(av2, (right_x, self.top_margin))
        else:
            pg.draw.rect(screen, p2.color, (right_x, self.top_margin, th2, th2), border_radius=6)
        screen.blit(name2, (right_x + th2 + self.name_avatar_gap, self.top_margin))
        self._draw_hp_bar(screen, right_x, bar_y, self.bar_w, self.bar_h, p2.hp, p2.max_hp)

        if winner:
            txt = self.font.render(f"{winner} WINS! Press ESC to quit.", True, (0, 0, 0))
            screen.blit(txt, (self.W // 2 - txt.get_width() // 2, bar_y + self.bar_h + 12))

# ---------------- 场景（给 main.py 调用） ----------------
class GameScene:
    """封装一局对战。通过回调把胜负结果返回主程序。"""
    def __init__(self, cfg: Dict[str, Any], screen: pg.Surface,
                 sprite1: Optional[str], sprite2: Optional[str],
                 on_game_end):
        self.cfg = cfg
        self.screen = screen
        self.on_game_end = on_game_end
        self.world = World(cfg)
        self.clock = pg.time.Clock()

        # 角色
        p1cfg, p2cfg = cfg["players"][0], cfg["players"][1]
        self.p1 = Fighter(p1cfg, self.world, override_sprite=sprite1)
        self.p2 = Fighter(p2cfg, self.world, override_sprite=sprite2)

        self.running = True
        self.winner: Optional[str] = None
        self._end_called = False
        self.frozen = False  # 结束后冻结更新与 flip，避免与弹窗刷新冲突

    def _resolve_collision_push(self):
        # 简单分离：矩形交叠时各退一半
        if self.p1.rect.colliderect(self.p2.rect):
            overlap = self.p1.rect.clip(self.p2.rect)
            if overlap.width > 0:
                self.p1.rect.x -= overlap.width // 2
                self.p2.rect.x += overlap.width // 2

    def _attack_and_hit(self):
        hb1 = self.p1.attack_hitbox()
        hb2 = self.p2.attack_hitbox()

        if hb1 and hb1.colliderect(self.p2.rect):
            # 根据相对位置决定击退方向：从右边打来则向右退
            from_right = self.p1.rect.centerx > self.p2.rect.centerx
            self.p2.get_hurt(self.world.damage, self.world.kb, from_right)

        if hb2 and hb2.colliderect(self.p1.rect):
            from_right = self.p2.rect.centerx > self.p1.rect.centerx
            self.p1.get_hurt(self.world.damage, self.world.kb, from_right)

    def step(self):
        # 定时
        self.clock.tick(self.world.FPS)

        # 事件
        for e in pg.event.get():
            if e.type == pg.QUIT:
                self.running = False
        keys = pg.key.get_pressed()
        if keys[pg.K_ESCAPE]:
            self.running = False

        # 冻结：只绘制，不更新，不 flip（由主循环统一 flip，避免闪烁）
        if self.frozen:
            self.world.draw_stage(self.screen)
            self.p1.draw(self.screen)
            self.p2.draw(self.screen)
            self.world.draw_ui(self.screen, self.p1, self.p2, self.winner)
            return self.running

        # 正常流程
        if not self.winner:
            self.p1.input(keys)
            self.p2.input(keys)

            self._resolve_collision_push()
            self.p1.physics()
            self.p2.physics()
            self._attack_and_hit()

            if self.p1.hp <= 0 or self.p2.hp <= 0:
                self.winner = self.p1.display_name if self.p2.hp <= 0 else self.p2.display_name
                if not self._end_called and self.on_game_end:
                    self._end_called = True
                    self.on_game_end(self.winner)
                # 结束后冻结，避免与弹窗抢刷新
                self.frozen = True

        # 绘制 & flip（仅进行中才 flip；冻结时由主循环 flip）
        self.world.draw_stage(self.screen)
        self.p1.draw(self.screen)
        self.p2.draw(self.screen)
        self.world.draw_ui(self.screen, self.p1, self.p2, self.winner)
        pg.display.flip()
        return self.running
