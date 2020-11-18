import mwparserfromhell as mw
import requests
import pickle
import atexit
import feedparser
from datetime import datetime

# Default values
treeDict = {}
lastUpdated = "2000-01-01T00:00:00Z"
API_URL = "https://en.wikipedia.org/w/api.php"


# A class to represent each part of the 'tree'. A node is either a genus or a clade. Each node has a name, rank, a parent node, a list of children and a list detailing its taxonomy.
class Node:
    def __init__(self, name, list, rank):
        self.name = name
        self.cladeList = list
        self.rank = rank
        try:
            self.parent = list[1]
        except:
            self.parent = ""
        self.children = []

    def addChild(self, child):
        self.children.append(child)

    def removeChild(self, child):
        if child in self.children:
            self.children.remove(child)

    def addRank(self, rank):
        self.rank = rank

    # Overridden methods
    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


# When the program goes through the tree, if it cannot find a string in the dictionary, it will look here for an alias instead.
aliases = {
    "Crocodylia": "Crocodilia",
    "Breviguartossa": "Breviquartossa",
    "Corythosaurini": "Lambeosaurini",
    "Ankylopoda": "Lepidosauromorpha",
    "Archelosauria": "Archosauromorpha",
    "Uraeus": "Naja (Uraeus)",
    "Afronaja": "Naja (Afronaja)",
    "Boulengerina": "Naja (Boulengerina)",
    "Cyclorinae": "Cyclocorinae",
}

# Wikipedia uses latin names for ranks in their templates, so this is needed when anglicising rank names.
replacements = {
    "regnum": "kingdom",
    "cladus": "clade",
    "classis": "class",
    "familia": "family",
    "ordo": "order",
    "tribus": "tribe",
}


# This puts the data in its correct place for processing
def loadData(treeTimeTuple):
    global lastUpdated
    global treeDict
    lastUpdated = treeTimeTuple[0]
    treeDict = treeTimeTuple[1]


# This ensures that the tree is saved every time the program closes
def exitHandler():
    global treeDict
    treeTimeTuple = (lastUpdated, treeDict)
    with open("tree.txt", "wb") as file:
        pickle.dump(treeTimeTuple, file, pickle.HIGHEST_PROTOCOL)


atexit.register(exitHandler)


# Takes in a page name and returns a parsed version of the page's contents
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


# Returns the value of a specified parameter for a specified page
def getTaxonData(pageName, data):
    pageName = "Template:Taxonomy/" + pageName
    page = parse(pageName)
    temps = page.filter_templates()
    temp = ""
    for t in temps:
        if t.has(data):
            temp = t
            break
    param = temp.get(data)
    paramData = param.split("=")[1]
    return paramData


# Removes dumb characters from the pagename like spaces or newlines
def cleanPageName(pageName):
    pageName = pageName.replace("/?", "")
    pageName = pageName.replace("/skip", "")
    pageName = pageName.replace("\r", "")
    pageName = pageName.strip()
    return pageName


def printTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    if pageName not in treeDict:
        if pageName in aliases:
            pageName = aliases[pageName]
        else:
            addTaxonTree(pageName)
            printTaxonTree(pageName)
    clades = treeDict[pageName].cladeList.copy()
    clades.reverse()
    for clade in clades:
        node = treeDict[clade]
        print(node.rank + " - " + str(node))


# Returns the list form of a taxon tree
def listTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    if pageName in treeDict:
        return treeDict[pageName].cladeList
    elif pageName in aliases:
        return treeDict[aliases[pageName]].cladeList
    else:
        addTaxonTree(pageName)
        return listTaxonTree(pageName)


# Adds a new taxon tree to the dictionary
def addTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    parent = getTaxonData(pageName, "parent")
    rank = cleanRank(getTaxonData(pageName, "rank"))
    result = [pageName] + listTaxonTree(parent)
    treeDict[pageName] = Node(pageName, result, rank)
    registerChild(pageName)


# Removes dumb characters from the rank, then anglicises it
def cleanRank(rank):
    rank = rank.strip()
    for rep in replacements:
        rank = rank.replace(rep, replacements[rep])
    return rank


# The main function of my original system, this takes two clade names and finds the deepest clade that is common to both
def commonClade(page1, page2):
    print("Generating list 1")
    list1 = listTaxonTree(page1).copy()
    list1.reverse()
    print("Generating list 2")
    list2 = listTaxonTree(page2).copy()
    list2.reverse()
    print("Comparing lists")
    st = ""
    counter = 0
    if (len(list1) > len(list2)):
        while len(list2) > 0:
            if list1[0] != list2[0]:
                break
            else:
                st = list1[0]
                list1 = list1[1:]
                list2 = list2[1:]
            counter += 1
    else:
        while len(list1) > 0:
            if list1[0] != list2[0]:
                break
            else:
                st = list1[0]
                list1 = list1[1:]
                list2 = list2[1:]
            counter += 1
    print("The deepest common clade between " + page1 + " and " + page2 + " is: " + st)
    print(page1 + " and " + page2 + " have " + str(counter) + " clades in common")
    print(page1 + " is " + str(len(list1)) + " clades deeper than " + st)
    print(page2 + " is " + str(len(list2)) + " clades deeper than " + st)


# Returns a list of pages that link to the given page, along with potentially an id for continuing the API request, if there are more pages that need to be listed
# Contains an optional 'subpageOnly' parameter if the output should not include the 'Template:Taxonomy/' before the page name
def backlinks(page, limit, cont="", subpageOnly=True):
    params = {
        "action": "query",
        "list": "backlinks",
        "bltitle": page,
        "blnamespace": 10,
        "bllimit": limit,
        "blfilterredir": "nonredirects",
        "format": "json",
        "formatversion": "2",
    }
    if cont != "":
        params["blcontinue"] = cont
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = req.json()
    text = res['query']['backlinks']
    contOut = -1
    output = []
    if "continue" in res:
        contOut = res['continue']['blcontinue']
    if subpageOnly:
        for var in text:
            spl = var['title'].split("/")
            if spl[0] == "Template:Taxonomy" and spl[1] != "Incertae sedis":
                output.append(spl[1])
    else:
        for var in text:
            spl = var['title'].split("/")
            if spl[0] == "Template:Taxonomy" and spl[1] != "Incertae sedis":
                output.append(var['title'])
    return output, contOut


# Adds the given page, as well as every clade below it, to the tree
def addAll(page):
    pages, cont = backlinks("Template:Taxonomy/" + page, 500)
    counter = 1
    for var in pages:
        if var not in treeDict and var not in aliases:
            addTaxonTree(var)
            print("Added item " + str(counter) + ": " + var)
        else:
            print("Item " + str(counter) + " already exists: " + var)
        counter += 1
    while cont != -1:
        pages, cont = backlinks("Template:Taxonomy/" + page, 500, cont=cont)
        for var in pages:
            if var not in treeDict and var not in aliases:
                addTaxonTree(var)
                print("Added item " + str(counter) + ": " + var)
            else:
                print("Item " + str(counter) + " already exists: " + var)
        counter += 1


# Deletes a node from the tree. Nodes with children cannot be deleted, for safety's sake.
def delNode(node):
    if node not in treeDict:
        print("Node not found")
        return
    elif len(treeDict[node].children) > 0:
        print("Node has children, cannot delete.")
        return
    else:
        treeDict[treeDict[node].parent].removeChild(node)
        del treeDict[node]


# Adds the given node to its parent's list of children
def registerChild(node):
    parent = treeDict[treeDict[node].parent]
    if node in parent.children:
        print("Child already registered")
    else:
        parent.addChild(node)


# Prints out a list of the children of a given node
def childrenOf(node, noGen=False):
    if noGen:
        outputList = []
        for var in treeDict[node].children:
            if treeDict[var].rank != "genus":
                outputList.append(var)
        print(outputList)
    else:
        print(treeDict[node].children)


# Prints out a list of all other nodes who are children of this node's parent
# The optional 'noGen' parameter can be used to only print out clades and exclude all genera
def sisterClades(clade, noGen=False):
    tempList = treeDict[treeDict[clade].parent].children.copy()
    tempList.remove(clade)
    if noGen:
        outputList = []
        for var in tempList:
            if treeDict[var].rank != "genus":
                outputList.append(var)
        print(outputList)
    else:
        print(tempList)


# Returns a count of how many genera are currently listed under the given clade
def countGenera(clade, counter=0):
    for var in treeDict[clade].children:
        if treeDict[var].rank == "genus":
            counter += 1
        else:
            counter = countGenera(var, counter)
    return counter


# Returns a list of all genera currently listed under the given clade
def listGenera(clade, currentList=None):
    if currentList is None:
        currentList = []
    for var in treeDict[clade].children:
        if treeDict[var].rank == "genus":
            currentList.append(var)
        else:
            currentList = listGenera(var, currentList)
    return currentList


# Forces the system to re-get the data for a given clade
def forceUpdate(clade):
    pageName = cleanPageName(clade)
    if pageName not in treeDict:
        addAll(pageName)
    else:
        treeDict[treeDict[pageName].parent].removeChild(pageName)
        addTaxonTree(pageName)
    print("Updated " + pageName)


# Updates the data of all pages that have been edited since the last check
def checkUpdates():
    global lastUpdated
    print("Checking for updates...")
    toUpdate = related(lastUpdated)

    if len(toUpdate) == 0:
        print("No updates found.")
    else:
        for var in toUpdate:
            forceUpdate(var)
    my_date = datetime.now()
    lastUpdated = my_date.isoformat()[:-7] + "Z"


# Returns a list of pages linking to Template:Taxonomy/Sauria that have been changed since the last check
# The optional target parameter can be used to specify a broader or narrower search for pages
def related(timestamp, target="Sauria"):
    params = {
        "action": "feedrecentchanges",
        "namespace": 10,
        "days": 1000,
        "limit": 50,
        "from": timestamp,
        "hidecategorization": True,
        "target": "Template:Taxonomy/" + target,
        "showlinkedto": True,
        "format": "json",
        "formatversion": "2",
    }
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = feedparser.parse(req.content)['entries']
    output = []
    for var in res:
        output.append(var['title'])
    return output


def importTree():
    with open("tree.txt", "rb") as file:
        # treeDict = pickle.load(file)
        treeTimeTuple = pickle.load(file)
        loadData(treeTimeTuple)

#DO NOT DELETE THIS LINE
if __name__ == "__main__":
    importTree()

# checkUpdates()

# childrenOf("Selachimorpha")
# print(len(backlinks("Template:Taxonomy/Pseudosuchia",5000)[0]))
# ("Octopoda","Selachimorpha")
# print(countGenera("Selachimorpha"))
