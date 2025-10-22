# -*- coding: utf-8 -*-
"""
游戏场景：对战逻辑 + UI（血条/头像/姓名）+ 纯矩形擂台
"""
import pygame as pg
from typing import Dict, Any, Optional
import os

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
    if name in name_map: return name_map[name]
    if len(name)==1 and "a"<=name<="z": return getattr(pg, f"K_{name}")
    if len(name)==1 and "0"<=name<="9": return getattr(pg, f"K_{name}")
    return pg.K_SPACE

# ---------------- 角色 ----------------
class Fighter:
    def __init__(self, cfg: Dict[str, Any], world, override_sprite: Optional[str] = None):
        self.world = world
        self.display_name = cfg.get("display_name", "player")
        w,h = cfg.get("size",[80,120])
        self.w,self.h = int(w),int(h)
        self.color = tuple(cfg.get("color",[255,255,255]))
        self.sprite_path = override_sprite if override_sprite else cfg.get("sprite_image","")
        self.sprite = load_image_optional(self.sprite_path,(self.w,self.h))
        self.avatar_raw = load_image_optional(self.sprite_path,None)
        start_x = int(cfg.get("start_x",100))
        self.facing_right = bool(cfg.get("facing_right",True))
        self.rect = pg.Rect(start_x, world.ground_y - self.h, self.w, self.h)
        self.hp = self.max_hp = int(cfg.get("hp",100))
        self.vx=self.vy=0.0; self.on_ground=True
        self.state="idle"; self.attack_timer=0; self.hitstop=0
        self.keys={k:key_from_name(v) for k,v in cfg.get("keys",{}).items()}

    def input(self,keys):
        if self.hitstop>0: return
        self.vx=0
        if keys[self.keys.get("L")]: self.vx=-self.world.move_speed; self.facing_right=False
        if keys[self.keys.get("R")]: self.vx=self.world.move_speed; self.facing_right=True
        if keys[self.keys.get("JUMP")] and self.on_ground:
            self.vy=self.world.jump_v; self.on_ground=False
        if keys[self.keys.get("ATK")] and self.attack_timer<=0:
            self.state="attack"; self.attack_timer=self.world.attack_total

    def physics(self):
        if self.hitstop>0: self.hitstop-=1; return
        self.rect.x+=int(self.vx)
        rx,ry,rw,rh=self.world.ring_rect
        self.rect.x=max(rx,min(self.rect.x,rx+rw-self.w))
        if not self.on_ground:
            self.vy+=self.world.gravity
            self.rect.y+=int(self.vy)
            if self.rect.bottom>=self.world.ground_y:
                self.rect.bottom=self.world.ground_y; self.vy=0; self.on_ground=True
        if self.attack_timer>0:
            self.attack_timer-=1
            if self.attack_timer==0: self.state="idle"

    def attack_hitbox(self):
        if self.state!="attack": return None
        elapsed=self.world.attack_total-self.attack_timer
        if self.world.startup<elapsed<=self.world.startup+self.world.active:
            w,h=self.world.hb_w,self.world.hb_h; y_off=self.world.hb_y
            if self.facing_right: return pg.Rect(self.rect.right,self.rect.y+y_off,w,h)
            else: return pg.Rect(self.rect.left-w,self.rect.y+y_off,w,h)
        return None

    def get_hurt(self,dmg,kb,from_right):
        if self.hitstop>0: return
        self.hp=max(0,self.hp-int(dmg))
        self.vx=(kb if from_right else -kb)
        self.hitstop=self.world.hitstop

    def draw(self,screen):
        if self.sprite:
            img=self.sprite if self.facing_right else pg.transform.flip(self.sprite,True,False)
            screen.blit(img,self.rect.topleft)
        else:
            pg.draw.rect(screen,self.color,self.rect,border_radius=6)
        nose_x=self.rect.centerx+(15 if self.facing_right else -15)
        pg.draw.circle(screen,(0,0,0),(nose_x,self.rect.centery-10),4)

# ---------------- 世界/舞台 ----------------
class World:
    def __init__(self,cfg: Dict[str, Any]):
        self.W,self.H=cfg["window"]["width"],cfg["window"]["height"]
        p=cfg["physics"]
        self.gravity=p["gravity"]; self.jump_v=p["jump_v"]
        self.move_speed=p["move_speed"]; self.hitstop=p["hitstop"]; self.FPS=p.get("fps",60)
        atk=cfg["attack"]
        self.startup=atk["startup"]; self.active=atk["active"]; self.recovery=atk["recovery"]
        self.attack_total=self.startup+self.active+self.recovery
        self.damage=atk["damage"]; self.kb=atk["knockback"]
        hb=atk["hitbox"]; self.hb_w=hb["w"]; self.hb_h=hb["h"]; self.hb_y=hb["y_offset"]
        stage=cfg["stage"]
        self.bg_color=tuple(stage["background_color"])
        self.bg_image=load_image_optional(stage.get("background_image",""),(self.W,self.H))
        self.ground_color=tuple(stage["ground_color"])
        ring=stage["ring"]
        self.ring_rect=[int(v) for v in ring["rect"]]
        self.ground_y=self.ring_rect[1]
        self.deck_color=tuple(ring["deck_color"]); self.edge_color=tuple(ring["edge_color"])
        ui=cfg.get("ui",{})
        # self.font = pg.font.SysFont(None,32)
        self.font = pg.font.SysFont("Microsoft YaHei", 32)
        # self.font_small = pg.font.SysFont(None,int(ui.get("font_small_size",24)))
        self.font_small = pg.font.SysFont("Microsoft YaHei", int(ui.get("font_small_size", 24)))
        self.left_margin=int(ui.get("left_margin",40))
        self.top_margin=int(ui.get("top_margin",24))
        self.bar_w=int(ui.get("bar_w",360)); self.bar_h=int(ui.get("bar_h",18))
        self.name_avatar_gap=int(ui.get("name_avatar_gap",8))
        self.name_bar_gap=int(ui.get("name_bar_gap",6))

    def draw_stage(self,screen):
        if self.bg_image: screen.blit(self.bg_image,(0,0))
        else: screen.fill(self.bg_color)
        rx,ry,rw,rh=self.ring_rect
        pg.draw.rect(screen,self.deck_color,(rx,ry,rw,rh))
        pg.draw.rect(screen,self.edge_color,(rx,ry,rw,rh),width=3)

    def _draw_hp_bar(self,screen,x,y,w,h,hp,maxhp):
        ratio = max(0.0, float(hp)/maxhp)
        pg.draw.rect(screen,(60,60,60),(x,y,w,h),border_radius=4)
        pg.draw.rect(screen,(220,60,60),(x,y,int(w*ratio),h),border_radius=4)
        pg.draw.rect(screen,(0,0,0),(x,y,w,h),2,border_radius=4)

    def draw_ui(self,screen,p1:Fighter,p2:Fighter,winner):
        left_x  = self.left_margin
        right_x = screen.get_width() - self.left_margin - self.bar_w
        bar_y   = self.top_margin + self.font_small.get_height() + self.name_bar_gap

        # 左
        name1 = self.font_small.render(p1.display_name, True, (0,0,0))
        th = name1.get_height()
        av1 = pg.transform.smoothscale(p1.avatar_raw, (th,th)) if p1.avatar_raw else None
        if av1: screen.blit(av1, (left_x, self.top_margin))
        else: pg.draw.rect(screen, p1.color, (left_x, self.top_margin, th, th), border_radius=6)
        screen.blit(name1, (left_x + th + self.name_avatar_gap, self.top_margin))
        self._draw_hp_bar(screen, left_x, bar_y, self.bar_w, self.bar_h, p1.hp, p1.max_hp)

        # 右
        name2 = self.font_small.render(p2.display_name, True, (0,0,0))
        th2 = name2.get_height()
        av2 = pg.transform.smoothscale(p2.avatar_raw, (th2,th2)) if p2.avatar_raw else None
        if av2: screen.blit(av2, (right_x, self.top_margin))
        else: pg.draw.rect(screen, p2.color, (right_x, self.top_margin, th2, th2), border_radius=6)
        screen.blit(name2, (right_x + th2 + self.name_avatar_gap, self.top_margin))
        self._draw_hp_bar(screen, right_x, bar_y, self.bar_w, self.bar_h, p2.hp, p2.max_hp)

        if winner:
            txt=self.font.render(f"{winner} WINS! Press ESC to quit.",True,(0,0,0))
            screen.blit(txt,(self.W//2-txt.get_width()//2, bar_y + self.bar_h + 12))

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

    def step(self):
        dt = self.clock.tick(self.world.FPS)
        for e in pg.event.get():
            if e.type == pg.QUIT:
                self.running = False
        keys = pg.key.get_pressed()
        if keys[pg.K_ESCAPE]:
            self.running = False

        if not self.winner:
            self.p1.input(keys); self.p2.input(keys)
            if self.p1.rect.colliderect(self.p2.rect):
                overlap=self.p1.rect.clip(self.p2.rect)
                if overlap.width>0:
                    self.p1.rect.x-=overlap.width//2; self.p2.rect.x+=overlap.width//2
            self.p1.physics(); self.p2.physics()
            hb1,hb2=self.p1.attack_hitbox(), self.p2.attack_hitbox()
            if hb1 and hb1.colliderect(self.p2.rect): self.p2.get_hurt(self.world.damage,self.world.kb,True)
            if hb2 and hb2.colliderect(self.p1.rect): self.p1.get_hurt(self.world.damage,self.world.kb,False)
            if self.p1.hp<=0 or self.p2.hp<=0:
                self.winner = self.p1.display_name if self.p2.hp<=0 else self.p2.display_name
                # 通知主程序（由主程序弹窗）
                self.on_game_end(self.winner)

        self.world.draw_stage(self.screen)
        self.p1.draw(self.screen); self.p2.draw(self.screen)
        self.world.draw_ui(self.screen, self.p1, self.p2, self.winner)
        pg.display.flip()
        return self.running
