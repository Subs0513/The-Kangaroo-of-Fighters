# -*- coding: utf-8 -*-
"""
主程序：主界面（开始游戏 / 作者信息） + 角色选择弹窗 + 游戏场景 + 结束弹窗
"""
import json, os, pygame as pg
from typing import Dict, Any, Optional
from ui import Button, Modal
from game import GameScene

# ——可选：用系统文件对话框选择图片（仅在点击按钮时初始化，避免多余窗口）
def ask_image_file() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.askopenfilename(
            title="选择角色图片",
            filetypes=[("图片", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("所有文件", "*.*")]
        )
        root.destroy()
        return path if path else None
    except Exception as e:
        print("[filedialog] 打开失败：", e)
        return None

def deep_update(base: dict, other: dict) -> dict:
    for k, v in other.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base

def load_config(path="config.json") -> Dict[str, Any]:
    DEFAULT = {
        "window": {"width": 960, "height": 540, "title": "袋鼠大乱斗 · 菜单版"},
        "physics": {"gravity":1.0,"jump_v":-18,"move_speed":6,"hitstop":6,"fps":60},
        "stage": {"background_color":[210,230,255],"background_image":"","ground_color":[80,160,80],
                  "ring":{"enabled":True,"rect":[120,340,720,140],"deck_color":[230,230,230],"edge_color":[40,40,40]}},
        "ui": {"font_small_size":24,"left_margin":40,"top_margin":24,"bar_w":360,"bar_h":18,
               "name_avatar_gap":8,"name_bar_gap":6,"button_w":220,"button_h":56},
        "players":[
            {"name":"P1","display_name":"player 1","start_x":240,"size":[80,120],"color":[255,200,80],
             "sprite_image":"","facing_right":True,"hp":100,"keys":{"L":"a","R":"d","JUMP":"w","ATK":"f"}},
            {"name":"P2","display_name":"player 2","start_x":640,"size":[80,120],"color":[80,200,255],
             "sprite_image":"","facing_right":False,"hp":100,"keys":{"L":"left","R":"right","JUMP":"up","ATK":"k"}}
        ],
        "attack":{"damage":8,"knockback":8,"startup":3,"active":8,"recovery":7,"hitbox":{"w":48,"h":24,"y_offset":30}},
        "author":{"name":"Author","email":"author@example.com","desc":"袋鼠大乱斗作者"}
    }
    cfg = DEFAULT.copy()
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                cfg = deep_update(cfg, json.load(f))
        except Exception as e:
            print("[config] 加载失败，使用默认：", e)
    else:
        print("[config] 未找到 config.json，使用默认配置。")
    return cfg

# ---------------- 主程序 ----------------
def main():
    pg.init()
    cfg = load_config("config.json")
    W,H = cfg["window"]["width"], cfg["window"]["height"]
    screen = pg.display.set_mode((W,H))
    pg.display.set_caption(cfg["window"]["title"])
    clock = pg.time.Clock()

    # font = pg.font.SysFont(None, 48)
    # small = pg.font.SysFont(None, 28)

    font = pg.font.SysFont("Microsoft YaHei", 48)
    small = pg.font.SysFont("Microsoft YaHei", 28)

    # 状态机
    STATE = "MENU"     # MENU / GAME
    game_scene: Optional[GameScene] = None

    # 角色选择（在弹窗里设置）
    chosen_p1: Optional[str] = None
    chosen_p2: Optional[str] = None

    # ——主菜单按钮
    btn_w = int(cfg["ui"].get("button_w", 220))
    btn_h = int(cfg["ui"].get("button_h", 56))
    start_btn = Button(pg.Rect(W//2 - btn_w//2, H//2 - 70, btn_w, btn_h),
                       "开始游戏", font, on_click=lambda: open_select_modal())
    about_btn = Button(pg.Rect(W//2 - btn_w//2, H//2 + 10, btn_w, btn_h),
                       "作者信息", font, on_click=lambda: open_about_modal())

    # ——全局弹窗（需要时创建）
    current_modal: Optional[Modal] = None

    def open_about_modal():
        nonlocal current_modal
        author = cfg.get("author", {})
        def drawer(surf: pg.Surface, rect: pg.Rect):
            lines = [
                f"作者：{author.get('name','N/A')}",
                f"邮箱：{author.get('email','N/A')}",
                f"简介：{author.get('desc','')}"
            ]
            y = rect.y
            for t in lines:
                t_surf = small.render(t, True, (0,0,0))
                surf.blit(t_surf, (rect.x, y))
                y += t_surf.get_height() + 6
        m = Modal((520, 260), "作者信息", font, drawer)
        ok = Button(pg.Rect(0,0,140,48), "确定", small, on_click=lambda: close_modal())
        m.add_button(ok)
        current_modal = m

    def open_select_modal():
        """角色图片选择弹窗：P1/P2分别选择本地图片，确认后进入游戏。"""
        nonlocal current_modal, chosen_p1, chosen_p2, STATE, game_scene
        chosen_p1 = None; chosen_p2 = None

        preview_p1 = None
        preview_p2 = None

        def drawer(surf: pg.Surface, rect: pg.Rect):
            nonlocal preview_p1, preview_p2
            # 标题行
            t1 = small.render("玩家1 图片：", True, (0,0,0))
            t2 = small.render("玩家2 图片：", True, (0,0,0))
            surf.blit(t1, (rect.x, rect.y))
            surf.blit(t2, (rect.x, rect.y + 120))

            # 预览框
            box1 = pg.Rect(rect.x, rect.y + 30, 140, 70)
            box2 = pg.Rect(rect.x, rect.y + 150, 140, 70)
            pg.draw.rect(surf, (230,230,230), box1); pg.draw.rect(surf, (0,0,0), box1, 1)
            pg.draw.rect(surf, (230,230,230), box2); pg.draw.rect(surf, (0,0,0), box2, 1)
            if preview_p1: surf.blit(preview_p1, (box1.x + (box1.w-preview_p1.get_width())//2,
                                                  box1.y + (box1.h-preview_p1.get_height())//2))
            if preview_p2: surf.blit(preview_p2, (box2.x + (box2.w-preview_p2.get_width())//2,
                                                  box2.y + (box2.h-preview_p2.get_height())//2))

        m = Modal((640, 420), "选择角色图片", font, drawer)

        def on_choose_p1():
            nonlocal chosen_p1, preview_p1
            path = ask_image_file()
            if path:
                chosen_p1 = path
                img = pg.image.load(path).convert_alpha()
                preview_p1 = pg.transform.smoothscale(img, (120, 60))

        def on_choose_p2():
            nonlocal chosen_p2, preview_p2
            path = ask_image_file()
            if path:
                chosen_p2 = path
                img = pg.image.load(path).convert_alpha()
                preview_p2 = pg.transform.smoothscale(img, (120, 60))

        # 左侧两个“选择图片”按钮
        m.add_button(Button(pg.Rect(0,0,160,48), "选择玩家1图片", small, on_click=on_choose_p1))
        m.add_button(Button(pg.Rect(0,0,160,48), "选择玩家2图片", small, on_click=on_choose_p2))

        def on_confirm():
            nonlocal STATE, game_scene, current_modal
            # 进入游戏（若任一为空则让游戏内回退为纯色）
            close_modal()
            STATE = "GAME"
            game_scene = GameScene(cfg, screen, chosen_p1, chosen_p2, on_game_end=open_end_modal)

        # 确认 / 取消
        m.add_button(Button(pg.Rect(0,0,140,48), "确认", small, on_click=on_confirm))
        m.add_button(Button(pg.Rect(0,0,140,48), "取消", small, on_click=lambda: close_modal()))
        current_modal = m

    def open_end_modal(winner_name: str):
        """游戏结束弹窗（由 GameScene 回调触发）"""
        nonlocal current_modal, STATE, game_scene, chosen_p1, chosen_p2
        def drawer(surf: pg.Surface, rect: pg.Rect):
            t = small.render(f"{winner_name} 获胜！", True, (0,0,0))
            surf.blit(t, (rect.x, rect.y))
        m = Modal((520, 220), "比赛结束", font, drawer)

        def rematch():
            nonlocal game_scene
            close_modal()
            # 重新开一局，沿用之前的两张图片
            game_scene = GameScene(cfg, screen, chosen_p1, chosen_p2, on_game_end=open_end_modal)

        def back_to_menu():
            nonlocal STATE, game_scene
            close_modal()
            STATE = "MENU"
            game_scene = None

        m.add_button(Button(pg.Rect(0,0,160,48), "再来一局", small, on_click=rematch))
        m.add_button(Button(pg.Rect(0,0,160,48), "主界面", small, on_click=back_to_menu))
        current_modal = m

    def close_modal():
        nonlocal current_modal
        current_modal = None

    running = True
    while running:
        dt = clock.tick(60)
        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            if current_modal:
                current_modal.handle_event(e)
            else:
                if STATE == "MENU":
                    start_btn.handle_event(e)
                    about_btn.handle_event(e)

        # 绘制
        screen.fill((240, 248, 255))
        if STATE == "MENU":
            title = font.render("袋鼠大乱斗", True, (0,0,0))
            screen.blit(title, (W//2 - title.get_width()//2, 120))
            start_btn.draw(screen)
            about_btn.draw(screen)

        elif STATE == "GAME":
            if game_scene:
                if not game_scene.step():
                    running = False

        # 顶层弹窗
        if current_modal:
            current_modal.draw(screen)

        pg.display.flip()

    pg.quit()

if __name__ == "__main__":
    main()

