import tkinter as tk
import commonCladeSystem as ccs
from commonCladeSystem import Node
import pickle

def outputText(text):
    outputArea["state"] = "normal"
    outputArea.delete(1.0,tk.END)
    outputArea.insert(1.0,text)
    outputArea["state"] = "disabled"

with open("tree.txt", "rb") as file:
    treeTimeTuple = pickle.load(file)
    ccs.loadData(treeTimeTuple)

window = tk.Tk()
window.geometry("800x600")
window.resizable(False, False)

textPanel = tk.Frame(window)
controlPanel = tk.Frame(window)

outputArea = tk.Text(textPanel,state="disabled",relief="solid")
outputArea.pack()

label = tk.Label(controlPanel,text=ccs.countGenera("Selachimorpha"))
label.pack()

testButton = tk.Button(controlPanel,command=lambda: outputText("Test text"))
testButton.pack()

textPanel.grid(row=0,column=0)
controlPanel.grid(row=0,column=1)

#DO NOT WRITE CODE AFTER THIS
window.mainloop()