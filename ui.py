# -*- coding: utf-8 -*-
import pygame as pg
from typing import Callable, Tuple

class Button:
    """简单按钮组件"""
    def __init__(self, rect: pg.Rect, text: str, font: pg.font.Font,
                 on_click: Callable[[], None], enabled: bool = True):
        self.rect = rect
        self.text = text
        self.font = font
        self.on_click = on_click
        self.enabled = enabled
        self.hovered = False

    def handle_event(self, e: pg.event.Event):
        if not self.enabled:
            return
        if e.type == pg.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(e.pos)
        elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
            if self.enabled and self.rect.colliderect(pg.Rect(e.pos, (1,1))):
                self.on_click()

    def draw(self, surf: pg.Surface):
        base = (70, 160, 240) if self.enabled else (150, 150, 150)
        col = (90, 180, 255) if self.hovered and self.enabled else base
        pg.draw.rect(surf, col, self.rect, border_radius=10)
        pg.draw.rect(surf, (0,0,0), self.rect, width=2, border_radius=10)
        txt = self.font.render(self.text, True, (0,0,0))
        surf.blit(txt, (self.rect.centerx - txt.get_width()//2,
                        self.rect.centery - txt.get_height()//2))

class Modal:
    """居中弹窗：绘制一个面板 + 标题 + 自定义内容 + 一排按钮"""
    def __init__(self, area: Tuple[int,int], title: str, font: pg.font.Font,
                 content_drawer: Callable[[pg.Surface, pg.Rect], None] | None = None):
        self.area = area   # (width, height)
        self.title = title
        self.font = font
        self.content_drawer = content_drawer
        self.buttons: list[Button] = []

    def rect(self, screen: pg.Surface) -> pg.Rect:
        w, h = self.area
        return pg.Rect((screen.get_width()-w)//2, (screen.get_height()-h)//2, w, h)

    def add_button(self, btn: Button):
        self.buttons.append(btn)

    def handle_event(self, e: pg.event.Event):
        for b in self.buttons:
            b.handle_event(e)

    def draw(self, screen: pg.Surface):
        r = self.rect(screen)
        # 半透明遮罩
        shade = pg.Surface(screen.get_size(), pg.SRCALPHA)
        shade.fill((0,0,0,120))
        screen.blit(shade, (0,0))
        # 面板
        pg.draw.rect(screen, (245,245,245), r, border_radius=12)
        pg.draw.rect(screen, (0,0,0), r, 2, border_radius=12)
        # 标题
        title_surf = self.font.render(self.title, True, (0,0,0))
        screen.blit(title_surf, (r.centerx - title_surf.get_width()//2, r.y + 12))
        # 内容区域
        content_rect = pg.Rect(r.x+20, r.y+20+title_surf.get_height()+10, r.w-40, r.h-40-title_surf.get_height()-60)
        if self.content_drawer:
            self.content_drawer(screen, content_rect)
        # 按钮区（底部）
        btn_y = r.bottom - 56
        total_w = sum(b.rect.w for b in self.buttons) + (len(self.buttons)-1)*12 if self.buttons else 0
        cur_x = r.centerx - total_w//2
        for b in self.buttons:
            b.rect.topleft = (cur_x, btn_y)
            b.draw(screen)
            cur_x += b.rect.w + 12
