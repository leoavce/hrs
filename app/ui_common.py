import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv, os, datetime

def export_tree_to_csv(tree: ttk.Treeview, base_name: str) -> str:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = os.path.join(os.getcwd(), 'exports'); os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f'{base_name}_{ts}.csv')
    cols = tree["columns"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for iid in tree.get_children():
            row = [tree.set(iid, c) for c in cols]; w.writerow(row)
    messagebox.showinfo("내보내기", f"CSV 저장: {path}")
    return path
