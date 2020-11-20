import tkinter as tk
from tkinter.ttk import Treeview

root = tk.Tk()

f1 = tk.Frame(root)
f2 = tk.Frame(root)

f1.grid(column=0, row=0, sticky="nsew")
f2.grid(column=1, row=0, sticky="n")
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

Treeview(f1).pack(expand=True, fill='y')
tk.Button(f2, text="DAT BUTTON IS IN F2").pack()
tk.Button(f2, text="DAT BUTTON IS IN F2").pack()
tk.Button(f2, text="DAT BUTTON IS IN F2").pack()

root.mainloop()