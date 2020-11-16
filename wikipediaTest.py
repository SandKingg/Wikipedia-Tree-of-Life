import mwparserfromhell as mw
import requests
import feedparser

API_URL = "https://en.wikipedia.org/w/api.php"

def parse(title):
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "rvlimit": 1,
        "titles": title,
        "format": "json",
        "formatversion": "2",
    }
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = req.json()
    revision = res["query"]["pages"][0]["revisions"][0]
    text = revision["slots"]["main"]["content"]
    return mw.parse(text)

def getParent(pageName):
    pageName = "Template:Taxonomy/"+pageName
    page = parse(pageName)
    temps = page.filter_templates()
    if not temps[0].has("parent"):
        for t in temps:
            if t.has("parent"):
                temp = t
                break
    else:
        temp = temps[0]
    paramParent = temp.get("parent")
    parent = paramParent.split("=")[1]
    return parent

def taxonTree(pageName,mode):
    mode = mode.lower()
    pageName = pageName.replace("/?","")
    pageName = pageName.replace("/skip","")
    pageName = pageName.replace("\n","")
    pageName = pageName.replace("\t","")
    pageName = pageName.replace("\r","")
    pageName = pageName.replace(" ","")
    if mode == "print":
        if(pageName != "Life"):
            print(pageName)
            parent = getParent(pageName)
            taxonTree(parent,"print")
        else:
            print("Life")
    elif mode == "list":
        if (pageName != "Life"):
            parent = getParent(pageName)
            return [pageName]+taxonTree(parent,"list")
        else:
            return ["Life"]

def commonClade(page1,page2):
    print("Generating list 1")
    list1 = taxonTree(page1,"list")
    list1.reverse()
    print("Generating list 2")
    list2 = taxonTree(page2,"list")
    list2.reverse()
    print("Comparing lists")
    str = ""
    while len(list1) > 0:
        if list1[0] != list2[0]:
            break
        else:
            str = list1[0]
            list1 = list1[1:]
            list2 = list2[1:]
    return str

def backlinks(page,limit,cont=""):
    params = {
        "action": "query",
        "list": "backlinks",
        "bltitle": page,
        "blnamespace": 10,
        "bllimit": limit,
        "format": "json",
        "formatversion": "2",
    }
    if cont != "":
        params["blcontinue"] = cont
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = req.json()
    text = res['query']['backlinks']
    if "continue" in res:
        cont = res['continue']['blcontinue']
        print(cont)
    for var in text:
        print(var['title'])

def related(limit):
    params = {
        "action": "feedrecentchanges",
        "namespace": 10,
        "days": 1000,
        "limit": limit,
        "from": "2020-07-05T17:28:57Z",
        "hidecategorization": True,
        "target": "Template:Taxonomy/Sauria",
        "showlinkedto": True,
        "format": "json",
        "formatversion": "2",
    }
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = feedparser.parse(req.content)['entries']
    for var in res:
        print(var['title'])

related(50)

#backlinks("Template:Taxonomy/Elasmosauridae",500)
#print(parse("Template:Taxonomy/Crocodylia")[0] == "#")