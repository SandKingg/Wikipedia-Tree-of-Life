import mwparserfromhell as mw
import requests
import pickle
import atexit
import feedparser
import sys
import re
from datetime import datetime

# Default values
treeDict = {}
lastUpdated = "2000-01-01T00:00:00Z"
API_URL = "https://en.wikipedia.org/w/api.php"


# A class to represent each part of the 'tree'. A node is either a genus or a clade. Each node has a name, rank, a parent node, a list of children and a list detailing its taxonomy.
class Node:
    def __init__(self, name, cladeList, rank):
        self.name = name
        self.cladeList = cladeList
        self.rank = rank
        self.commonName = ""
        self.skip = False
        try:
            self.parent = cladeList[1]
        except:
            self.parent = ""
        self.children = []
        self.lastUpdated = datetime.now().isoformat()[:-7] + "Z"

    def addChild(self, child):
        self.children.append(child)

    def setParent(self, parent):
        self.parent = parent

    def setRank(self, rank):
        self.rank = rank

    def setCladeList(self, cladeList):
        self.cladeList = cladeList

    def setCommonName(self, commonName):
        self.commonName = commonName

    def removeChild(self, child):
        if child in self.children:
            self.children.remove(child)

    def flagSkip(self):
        self.skip = True

    def markUpdated(self):
        self.lastUpdated = datetime.now().isoformat()[:-7] + "Z"

    # Overridden methods
    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


# When the program goes through the tree, if it cannot find a string in the dictionary, it will look here for an alias or common name instead.
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
    "Sternidae": "Sternini",
    "Aegypiinae": "Gypinae",
    "Gypiinae": "Gypinae",
    "Odocoileinae": "Capreolinae",
    "Euungulata": "Ungulata",
    "Anteosauroidea": "Anteosauria",
    "\"Haptodus\"": "Haptodus",
    "Hapsidopareiontidae": "Hapsidopareiidae",
    "Keraterpetontidae": "Diplocaulidae",
    "Zatracheidae": "Zatrachydidae",
    "Chirixalus": "Chiromantis",
    "Plesiosuchia": "Plesiosuchina"
}
commonNames = {}

# Wikipedia uses latin names for ranks in their templates, so this is needed when anglicising rank names.
replacements = {
    "regnum": "kingdom",
    "cladus": "clade",
    "classis": "class",
    "familia": "family",
    "ordo": "order",
    "tribus": "tribe",
    "divisio": "division",
}

# Things that break this. Fix later.
dumbStuff = []

# This puts the data in its correct place for processing
def loadData(fileTuple):
    global lastUpdated
    global treeDict
    global commonNames
    lastUpdated = fileTuple[0]
    treeDict = fileTuple[1]
    try:
        commonNames = fileTuple[2]
    except:
        pass


# This ensures that the tree is saved every time the program closes
def exitHandler():
    global treeDict
    fileTuple = (lastUpdated, treeDict, commonNames)
    with open("tree.txt", "wb") as file:
        pickle.dump(fileTuple, file, pickle.HIGHEST_PROTOCOL)


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
    pageName = pageName.replace("?", "")
    pageName = pageName.replace("/displayed", "")
    pageName = pageName.replace("/skip", "")
    pageName = pageName.replace("/Class", "")
    pageName = pageName.replace("\r", "")
    pageName = pageName.replace("/\"", "")
    pageName = pageName.replace("Incertae sedis/", "")
    pageName = re.sub("<!--.*-->","",pageName)
    pageName = pageName.strip()
    return pageName


# Checks if the given string is a common name for a taxon (e.g. Spider for Aranea)
# Guarantees that the true taxon will be in the tree, if it exists
def checkCommonName(pageName):
    found = False
    try:
        page = parse(pageName)
        temps = page.filter_templates()
        temp = ""
        for t in temps:
            if t.name.matches("Automatic taxobox") and t.has("taxon"):
                temp = t
                found = True
                break
        if found:
            taxonParam = temp.get("taxon")
            taxon = taxonParam.split("=")[1]
            cleanTaxon = cleanPageName(taxon)
            if cleanTaxon not in treeDict:
                addTaxonTree(cleanTaxon)
            commonNames[pageName] = cleanTaxon
            treeDict[cleanTaxon].setCommonName(pageName)
    except KeyError:
        pass
    return found


# Attempts to parse 'Template:Taxonomy/<pageName>' as a Wikipedia page and returns whether it succeeds or not
def checkTaxonomyTemplate(pageName):
    pageName = cleanPageName(pageName)
    found = False
    try:
        pageName = "Template:Taxonomy/" + pageName
        parse(pageName)
        found = True
    except KeyError:
        pass
    return found


# Prints out a taxon tree
def printTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    if pageName not in treeDict:
        if pageName in aliases:
            pageName = aliases[pageName]
        elif pageName in commonNames:
            pageName = commonNames[pageName]
        elif checkTaxonomyTemplate(pageName):
            addTaxonTree(pageName)
        elif checkCommonName(pageName):
            pageName = commonNames[pageName]
        else:
            print(pageName + " is not a valid taxon or common name.")
            sys.exit()
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
    elif pageName in commonNames:
        return treeDict[commonNames[pageName]].cladeList
    elif checkTaxonomyTemplate(pageName):
        addTaxonTree(pageName)
        return listTaxonTree(pageName)
    elif checkCommonName(pageName):
        return treeDict[commonNames[pageName]].cladeList
    else:
        print(pageName + " is not a valid taxon or common name.")
        sys.exit()


# Adds a new taxon tree to the dictionary
def addTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    parent = cleanPageName(getTaxonData(pageName, "parent"))
    rank = cleanRank(getTaxonData(pageName, "rank"))
    result = [pageName] + listTaxonTree(parent)
    treeDict[pageName] = Node(pageName, result, rank)
    registerChild(pageName)


# Removes dumb characters from the rank, then anglicises it
def cleanRank(rank):
    rank = rank.strip()
    rank = re.sub("<!--.*-->","",rank)
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
    if len(list1) > len(list2):
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
    for var in text:
        spl = var['title'].split("/")
        if spl[0] == "Template:Taxonomy" and spl[1] != "Incertae sedis" and spl[1] not in dumbStuff:
            if subpageOnly:
                output.append(spl[1])
            else:
                output.append(var['title'])
    return output, contOut


# Adds the given page, as well as every clade below it, to the tree
def addAll(page):
    pages, cont = backlinks("Template:Taxonomy/" + page, 500)
    counter = 1
    while True:
        for var in pages:
            if "/skip" in var:
                cleanVar = cleanPageName(var)
                if cleanVar == page:
                    continue
                if cleanVar in treeDict and treeDict[cleanVar].skip:
                    print("Found completed /skip. Skipping item " + str(counter) + ": " + cleanVar)
                else:
                    print("Found incomplete /skip. Now running addAll(" + cleanVar + ").")
                    addAll(cleanVar)
                    treeDict[cleanVar].flagSkip()
                    print("Added all subpages for item " + str(counter) + ": " + var)
            else:
                if var not in treeDict and var not in aliases:
                    addTaxonTree(var)
                    print("Added item " + str(counter) + ": " + var)
                else:
                    print("Item " + str(counter) + " already exists: " + var)
            counter += 1

        if cont == -1:
            break
        else:
            pages, cont = backlinks("Template:Taxonomy/" + page, 500, cont=cont)


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
        if "genus" in treeDict[var].rank:
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
        refreshData(pageName,True)
        refreshChildren(pageName)
    print("Updated " + pageName)


# Refreshes the data of a given node
def refreshData(name, allData=False):
    node = treeDict[name]
    if allData:
        node.markUpdated()
        newParent = cleanPageName(getTaxonData(name, "parent"))
        newRank = cleanRank(getTaxonData(name, "rank"))

        if newParent != node.parent:
            if newParent in aliases:
                newParent = aliases[newParent]
            elif newParent not in treeDict:
                addTaxonTree(newParent)
            treeDict[node.parent].removeChild(name)
            node.setParent(newParent)
            registerChild(name)

        if newRank != node.rank:
            node.setRank(newRank)

    node.setCladeList([name] + listTaxonTree(node.parent))


# Traverses the tree to refresh the data of all child nodes
def refreshChildren(name, allData=False):
    refreshData(name,allData)
    for child in treeDict[name].children:
        refreshChildren(child,allData)


# Updates the data of all pages that have been edited since the last check
def checkUpdates():
    global lastUpdated
    print("Checking for updates...")
    toUpdate = related(lastUpdated)
    my_date = datetime.now()
    lastUpdated = my_date.isoformat()[:-7] + "Z"

    if len(toUpdate) == 0:
        print("No updates found.")
    else:
        if len(toUpdate) == 50:
            print("Maximum limit reached for update auto-checking. Running fullUpdate() is suggested.")
        for var in toUpdate:
            forceUpdate(var)


# Returns a list of pages linking to Template:Taxonomy/Animalia that have been changed since the last check
def related(timestamp):
    params = {
        "action": "feedrecentchanges",
        "namespace": 10,
        "days": 1000,
        "limit": 50,
        "from": timestamp,
        "hidecategorization": True,
        "target": "Template:Taxonomy/Nephrozoa",
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


# Returns a pair consisting of the deepest clade from the given node and its depth from that node
def deepestFrom(name,depth=0):
    node = treeDict[name]
    deepestNode = name
    maxDepth = depth

    for var in node.children:
        testNode, testDepth = deepestFrom(treeDict[var].name,depth+1)
        if testDepth > maxDepth:
            maxDepth = testDepth
            deepestNode = testNode

    return deepestNode,maxDepth


# Takes in a list of 50 or fewer names and returns a list of those that need updating
def checkListForUpdates(toCheck):
    joinedList = "|".join(toCheck)
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": joinedList,
        "rvprop": "timestamp",
        "format": "json",
        "formatversion": "2",
    }
    headers = {"User-Agent": "My-Bot-Name/1.0"}
    req = requests.get(API_URL, headers=headers, params=params)
    res = req.json()["query"]["pages"]
    revisions = []
    output = []
    for id in res:
        try:
            revisions.append(id["revisions"][0]["timestamp"])
        except KeyError:
            name = id["title"]
            print(name + " has caused an error. The page likely does not exist.")
            revisions.append(datetime.now().isoformat()[:-7] + "Z")  # A dummy date so the list is the correct size
    try:
        for var in range(len(toCheck)):
            name = toCheck[var].split("/")[1]
            if treeDict[name].lastUpdated < revisions[var]:
                output.append(name)
        return output
    except:
        print("Error.")


# A long winded check for updates
def fullUpdate(root="Vertebrata"):
    #Step 1 - add any new pages that weren't caught
    addAll(root)
    #Step 1.5 - remember to check skip templates
    addAll("Aves")  # remove once we get to Chordata
    addAll("Aves/skip")  # remove once we get to Chordata
    #addAll("Bombycina") (skips to Lepidoptera)

    print("Looking for pages that need updating...")
    #Step 2 - Get a list of pages that need updating
    ary = []
    needsUpdating = []
    for var in treeDict:
        ary.append("Template:Taxonomy/" + var)
    while len(ary) > 50:
        tempAry = []
        for var in range(50):
            tempAry.append(ary.pop(0))
        needsUpdating += checkListForUpdates(tempAry)
    needsUpdating += checkListForUpdates(ary)

    if len(needsUpdating) > 0:
        print("Updating pages...")
        #Step 3 - Update everything that needs updating
        for node in needsUpdating:
            if node != "Life":
                refreshData(node, True)
                refreshChildren(node)
    else:
        print("Nothing to update.")


# Prints a line-by-line representation of a tree
def treeReport(root,max=-1,depth=0):
    indent = ""
    for var in range(depth):
        indent += "\t"
    print(indent + root)

    if max == -1 or depth < max:
        for var in treeDict[root].children:
            treeReport(var,max,depth+1)


# Goes through the default startup routine, importing the tree from the file and setting lastUpdated
def importTree():
    with open("tree.txt", "rb") as file:
        # treeDict = pickle.load(file)
        fileTuple = pickle.load(file)
        loadData(fileTuple)

#DO NOT DELETE THIS CODE
if __name__ == "__main__":
    importTree()
    checkUpdates()

    #Put actual commands below here
    treeReport("Testudinata",2)

    """output = []
    links, cont = backlinks("Template:Taxonomy/Nephrozoa",500,subpageOnly=False)
    for var in links:
        if "/skip" in var:
            output.append(var)
    while cont != -1:
        links, cont = backlinks("Template:Taxonomy/Nephrozoa", 500, cont=cont, subpageOnly=False)
        for var in links:
            if "/skip" in var:
                output.append(var)
    print(output)"""


# childrenOf("Selachimorpha")
# print(len(backlinks("Template:Taxonomy/Pseudosuchia",5000)[0]))
# ("Octopoda","Selachimorpha")
# print(countGenera("Selachimorpha"))
