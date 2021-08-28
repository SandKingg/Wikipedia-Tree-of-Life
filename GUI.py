import tkinter as tk
from tkinter import ttk
import commonCladeSystem as ccs
from commonCladeSystem import Node
import pickle

'''def outputText(text):
    outputArea["state"] = "normal"
    outputArea.delete(1.0,tk.END)
    outputArea.insert(1.0,text)
    outputArea["state"] = "disabled"'''


def loadTree(name="Sauria"):
    node = ccs.treeDict[name]
    text = name
    if hasattr(node, "commonName") and node.commonName != "":
        text += " [" + node.commonName + "]"
    if "genus" not in node.rank:
        text += " (" + str(ccs.countGenera(name)) + ")"
    tree.insert(node.parent, 'end', name, text=text)
    tree.set(name,"rank",node.rank)
    for var in node.children:
        loadTree(var)

with open("tree.txt", "rb") as file:
    treeTimeTuple = pickle.load(file)
    ccs.loadData(treeTimeTuple)

window = tk.Tk()
window.geometry("1000x700")

window.rowconfigure(0, weight=1)
window.columnconfigure(0, weight=1)

tree = ttk.Treeview(window, height=10, columns="rank")
tree.grid(row=0, column=0, sticky=tk.NSEW)

tree.column("#0", width=0, stretch = True, minwidth=80)
tree.column("rank", width=100)
tree.heading("#0", text="Tree of Sauria")
tree.heading("rank", text="Rank")

scrollHoriz = ttk.Scrollbar(window, orient=tk.HORIZONTAL, command=tree.xview)
scrollVert = ttk.Scrollbar(window, orient=tk.VERTICAL, command=tree.yview)
scrollHoriz.grid(row=1,column=0,sticky=tk.EW)
scrollVert.grid(row=0,column=1,sticky=tk.NS)
tree.configure(xscrollcommand=scrollHoriz.set, yscrollcommand=scrollVert.set)

tree.insert('', 0, "Neodiapsida", text="Neodiapsida")
loadTree()

# DO NOT WRITE CODE AFTER THIS
window.mainloop()
