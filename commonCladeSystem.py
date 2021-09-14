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
    def __init__(self, name, cladeList, rank, extinct):
        self.name = name
        self.cladeList = cladeList
        self.rank = rank
        self.extinct = extinct
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

    def setExtinct(self, extinct):
        self.extinct = extinct

    def setCladeList(self, cladeList):
        self.cladeList = cladeList

    def setCommonName(self, commonName):
        self.commonName = commonName

    def removeCommonName(self):
        self.commonName = ""

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
    "Plesiosuchia": "Plesiosuchina",
    "Cyclostomi": "Cyclostomata"
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
    pageName = addTemplate(pageName)

    page = parse(pageName)
    temps = page.filter_templates()
    for t in temps:
        if t.has(data):
            param = t.get(data)
            paramData = param.split("=")[1]
            return paramData


# Returns the value of the 'extinct' parameter for a specified page
def getExtinct(pageName):
    pageName = addTemplate(pageName)

    page = parse(pageName)
    temps = page.filter_templates()
    temp = ""
    found = False
    for t in temps:
        if t.has("extinct"):
            temp = t
            found = True
            break
    if found:
        param = temp.get("extinct").lower()
        paramData = cleanPageName(param.split("=")[1])
    return found and (paramData == "yes" or paramData == "true")


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
    pageName = pageName.replace("_", " ")
    pageName = re.sub("<.*>", "", pageName)  # Removes HTML comments as well as HTML tags
    pageName = re.sub("<.*", "", pageName)  # In case splitting splits on an = inside the tags
    pageName = pageName.strip()
    return pageName


# Removes dumb characters from the rank, then anglicises it
def cleanRank(rank):
    rank = rank.strip()
    rank = re.sub("<!--.*-->", "", rank)
    for rep in replacements:
        rank = rank.replace(rep, replacements[rep])
    return rank


# Turns a 'name' into a 'Template:Taxonomy/name' and does nothing otherwise
def addTemplate(pageName):
    splitTest = pageName.split("/")
    if len(splitTest) == 1:
        pageName = "Template:Taxonomy/" + pageName
    return pageName


# Parses a page and follows a redirect if it exists, returning a parsed page
def parseAndRedirect(pageName):
    page = parse(pageName)
    if "#redirect" in page.lower():
        m = re.search("#redirect\s*\[\[(.*)\]\]", str(page), re.IGNORECASE)
        redirect = m.group(1)
        page = parse(redirect)
    return page


# Registers a common name for a given taxon
def registerCommonName(taxon, common):
    commonNames[common] = taxon
    treeDict[taxon].setCommonName(common)


# Removes a common name from a given taxon
def removeCommonName(taxon):
    node = treeDict[taxon]
    commonName = node.commonName
    if commonName == "":
        print("No common name exists for " + taxon)
    else:
        node.removeCommonName()
        commonNames.pop(commonName)
        print("Removed the common name '" + commonName + "' for " + taxon)


# Searches for common names for the genera below a given taxon.
# If children is true, it looks at every first-level child whether a genus or not
def searchCommonNames(taxon, children=False):
    if children:
        list = childrenOf(taxon)
    else:
        list = listGenera(taxon)
    for name in list:
        clade = treeDict[name]
        if hasattr(clade, "commonName") and clade.commonName != "":
            print("Common name '" + clade.commonName + "' already exists for " + name)
            continue
        try:
            link = cleanPageName(getTaxonData(name, "link"))
            if link != name:
                ccn = checkCommonName(link)
                if ccn:
                    print("Common name '" + link + "' added for " + name)
                else:
                    print("No common name found for " + name)
            else:
                page = parse(link)
                if "#redirect" in page.lower():
                    m = re.search("#redirect\s*\[\[(.*)\]\]", str(page), re.IGNORECASE)
                    redirect = m.group(1)
                    ccn = checkCommonName(redirect)
                    if ccn:
                        print("Common name '" + redirect + "' added for " + name)
                    else:
                        print("No common name found for " + name)
        except KeyError:
            continue


# Checks if the given string is a common name for a taxon (e.g. Spider for Aranea)
# Guarantees that the true taxon will be in the tree, if it exists
def checkCommonName(pageName):
    if pageName in treeDict:
        return False
    found = False
    try:
        page = parse(pageName)
        if "#redirect" in page.lower():
            m = re.search("#redirect\s*\[\[(.*)\]\]", str(page), re.IGNORECASE)
            redirect = m.group(1)
            if redirect in treeDict or checkTaxonomyTemplate(redirect):
                taxon = redirect
                found = True
        else:
            temps = page.filter_templates()
            for t in temps:
                name = cleanPageName(str(t.name))
                if name.lower() == "automatic taxobox" and t.has("taxon"):
                    found = True
                    taxonParam = t.get("taxon")
                    taxon = taxonParam.split("=")[1]
                    break
        if found:
            cleanTaxon = cleanPageName(taxon)
            if cleanTaxon not in treeDict:
                addTaxonTree(cleanTaxon)
            registerCommonName(cleanTaxon, pageName)
    except KeyError:
        pass
    return found


# Attempts to parse 'Template:Taxonomy/<pageName>' as a Wikipedia page and returns whether it succeeds or not
def checkTaxonomyTemplate(pageName):
    pageName = cleanPageName(pageName)
    found = False
    try:
        tempPageName = addTemplate(pageName)
        content = parse(tempPageName)
        if "#redirect" not in content.lower():
            found = True
    except KeyError:
        pass
    return found


# Checks if <pageName> has the speciesbox or subspeciesbox templates on its page
# Returns 1 for species, 2 for subspecies, 0 for non-species
def checkSpecies(pageName):
    pageName = cleanPageName(pageName)
    try:
        page = parseAndRedirect(pageName)
        temps = page.filter_templates()
        for t in temps:
            name = cleanPageName(str(t.name))
            if name.lower() == "speciesbox":
                return 1
            elif name.lower() == "subspeciesbox":
                return 2
    except KeyError:
        pass
    return 0


# Gets the taxon for a given species and returns it as both genus and species
def getSpeciesTaxon(species):
    pageName = cleanPageName(species)
    page = parseAndRedirect(pageName)
    temps = page.filter_templates()
    for t in temps:
        name = cleanPageName(str(t.name))
        if name.lower() == "speciesbox":  # TODO: Check for speciesboxes with the subgenus parameter
            if t.has("taxon"):
                param = t.get("taxon")
                paramData = cleanPageName(param.split("=")[1])
                genus = paramData.split()[0]
                species = paramData.split()[1]
            else:
                param1 = t.get("genus")
                param2 = t.get("species")
                genus = cleanPageName(param1.split("=")[1])
                species = cleanPageName(param2.split("=")[1])
            return genus, species
        elif name.lower() == "subspeciesbox":
            # Wikipedia says subspeciesbox requires the taxon in parts
            param1 = t.get("genus")
            param2 = t.get("species")
            param3 = t.get("subspecies")
            genus = cleanPageName(param1.split("=")[1])
            species = cleanPageName(param2.split("=")[1])
            subspecies = cleanPageName(param3.split("=")[1])
            return genus, species, subspecies


# Gets whether a given species/subspecies is extinct or not
def getSpeciesExtinct(clade):
    pageName = cleanPageName(clade)
    page = parseAndRedirect(pageName)
    temps = page.filter_templates()
    for t in temps:
        name = cleanPageName(str(t.name))
        if "speciesbox" in name.lower():
            if t.has("extinct"):
                return True
    return False


# Prints out a taxon tree
def printTaxonTree(pageName, mainRanksOnly=False):
    clades = listTaxonTree(pageName).copy()
    clades.reverse()
    mainRanks = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
    for clade in clades:
        if clade in treeDict:
            node = treeDict[clade]
            if (not mainRanksOnly) or (node.rank in mainRanks) or (clade == pageName):
                print(node.rank + " - " + clade)
        elif treeDict[clade.split()[0]].rank == "genus":
            taxonArray = clade.split()
            if len(taxonArray) == 2:
                print("species - " + clade)
            elif len(taxonArray) == 3:
                print("subspecies - " + clade)


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
    elif checkSpecies(pageName) == 1:
        genus, species = getSpeciesTaxon(pageName)
        addSpecies(genus, species)
        clade = genus + " " + species
        if pageName != clade:
            registerCommonName(clade, pageName)
        return listTaxonTree(clade)
    elif checkSpecies(pageName) == 2:
        genus, species, subspecies = getSpeciesTaxon(pageName)
        addSpecies(genus, species, subspecies)
        clade = genus + " " + species + " " + subspecies
        if pageName != clade:
            registerCommonName(clade, pageName)
        return listTaxonTree(clade)
    else:
        print(pageName + " is not a valid taxon or common name.")
        sys.exit()


# Adds a new taxon tree to the dictionary
def addTaxonTree(pageName):
    pageName = cleanPageName(pageName)
    parent = cleanPageName(getTaxonData(pageName, "parent"))
    rank = cleanRank(getTaxonData(pageName, "rank"))
    extinct = getExtinct(pageName)
    result = [pageName] + listTaxonTree(parent)
    treeDict[pageName] = Node(pageName, result, rank, extinct)
    registerChild(pageName)


# Specialised function for adding species or subspecies to the tree, as they do not use Template:Taxobox
def addSpecies(genus, species, subspecies=""):
    clade = genus + " " + species + " " + subspecies
    clade = clade.strip()
    if clade in treeDict:
        return

    if treeDict[genus].extinct:
        extinct = True
    else:
        extinct = getSpeciesExtinct(clade)

    if subspecies == "":
        result = [clade] + listTaxonTree(genus)
        rank = "species"
    else:
        result = [clade] + listTaxonTree(genus + " " + species)
        rank = "subspecies"
    treeDict[clade] = Node(clade, result, rank, extinct)
    registerChild(clade)


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
        print("Node deleted")


# Adds the given node to its parent's list of children
def registerChild(node):
    parent = treeDict[treeDict[node].parent]
    if node in parent.children:
        print("Child already registered")
    else:
        parent.addChild(node)


# Returns a list of the children of a given node
def childrenOf(node, noGen=False):
    if noGen:
        outputList = []
        for var in treeDict[node].children:
            if treeDict[var].rank != "genus":
                outputList.append(var)
        return outputList
    else:
        return treeDict[node].children


# Returns a list of all other nodes who are children of this node's parent
# The optional 'noGen' parameter can be used to only print out clades and exclude all genera
def sisterClades(clade, noGen=False):
    tempList = treeDict[treeDict[clade].parent].children.copy()
    tempList.remove(clade)
    if noGen:
        outputList = []
        for var in tempList:
            if treeDict[var].rank != "genus":
                outputList.append(var)
        return outputList
    else:
        return tempList


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
    pageName = pageName.replace("Template:Taxonomy/", "")
    if pageName not in treeDict:
        addTaxonTree(pageName)
    else:
        refreshData(pageName, True)
        refreshChildren(pageName)
    print("Updated " + pageName)


# Refreshes the data of a given node
def refreshData(name, allData=False):
    name = name.replace("Template:Taxonomy/", "")
    node = treeDict[name]
    if allData:
        try:
            newParent = cleanPageName(getTaxonData(name, "parent"))
            newRank = cleanRank(getTaxonData(name, "rank"))
            newExtinct = getExtinct(name)

            if newParent != node.parent:
                if newParent in aliases:
                    newParent = aliases[newParent]
                elif newParent not in treeDict:
                    addTaxonTree(newParent)
                treeDict[node.parent].removeChild(name)
                node.setParent(newParent)
                registerChild(name)

            node.setRank(newRank)
            node.setExtinct(newExtinct)

            node.markUpdated()
        except AttributeError:
            print("Error when updating " + name)

    node.setCladeList([name] + listTaxonTree(node.parent))


# Traverses the tree to refresh the data of all child nodes
def refreshChildren(name, allData=False):
    refreshData(name, allData)
    for child in treeDict[name].children:
        refreshChildren(child, allData)


# Updates the data of all pages that have been edited since the last check
# Now deprecated, but keeping it around just in case
"""def checkUpdates():
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
            forceUpdate(var)"""


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
def deepestFrom(name, depth=0):
    node = treeDict[name]
    deepestNode = name
    maxDepth = depth

    for var in node.children:
        testNode, testDepth = deepestFrom(treeDict[var].name, depth + 1)
        if testDepth > maxDepth:
            maxDepth = testDepth
            deepestNode = testNode

    return deepestNode, maxDepth


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
    names = []
    output = []
    for id in res:
        name = id["title"]
        names.append(name)
        try:
            revisions.append(id["revisions"][0]["timestamp"])
        except KeyError:
            print(name + " has caused an error. The page likely does not exist.")
            revisions.append(datetime.now().isoformat()[:-7] + "Z")  # A dummy date so the list is the correct size

    for var in range(len(names)):  # Needs to be names because the order isn't guaranteed to be the same as toCheck
        name = names[var].split("/")[1]
        if treeDict[name].lastUpdated < revisions[var]:
            output.append(name)
    return output


# A long winded check for updates
def fullUpdate(root="Vertebrata"):
    # Step 1 - add any new pages that weren't caught
    addAll(root)
    # Step 1.5 - remember to check skip templates
    addAll("Aves")  # remove once we get to Chordata
    addAll("Aves/skip")  # remove once we get to Chordata
    # addAll("Bombycina") (skips to Lepidoptera)

    print("Looking for pages that need updating...")
    # Step 2 - Get a list of pages that need updating
    ary = []
    needsUpdating = []
    for var in treeDict:
        if treeDict[var].rank != "species" and treeDict[var].rank != "subspecies":
            ary.append("Template:Taxonomy/" + var)

    length = len(ary)
    iterations = (length // 50) + 1  # +1 to get the ceiling
    iterCounter = 1
    while len(ary) > 50:
        print("Checking set " + str(iterCounter) + " of " + str(iterations))
        tempAry = []
        for var in range(50):
            tempAry.append(ary.pop(0))
        needsUpdating += checkListForUpdates(tempAry)
        iterCounter += 1
    print("Checking set " + str(iterations) + " of " + str(iterations))
    needsUpdating += checkListForUpdates(ary)

    if len(needsUpdating) > 0:
        print("Updating pages...")
        # Step 3 - Update everything that needs updating
        for node in needsUpdating:
            if node != "Life":
                refreshData(node, True)
                refreshChildren(node)
                print("Updated " + node)
    else:
        print("Nothing to update.")


# Prints a line-by-line representation of a tree
def printTreeReport(root, max=-1, depth=0, noExtinct=False):
    if noExtinct and treeDict[root].extinct:
        return

    indent = ""
    for var in range(depth):
        indent += "\t"
    clade = treeDict[root]
    if hasattr(clade, "commonName") and clade.commonName != "":
        print(indent + clade.commonName + " (" + root + ")")
    else:
        print(indent + root)

    if max == -1 or depth < max:
        for var in clade.children:
            printTreeReport(var, max, depth + 1, noExtinct)


# Creates a tree report in a file
def fileTreeReport(root, max=-1, noExtinct=False):
    if noExtinct and treeDict[root].extinct:
        return

    name = "Reports/" + root
    if max != -1:
        name += str(max)
    if noExtinct:
        name += " (Extant)"
    name += ".txt"

    stack = [(root, 0)]
    with open(name, "w") as file:
        while stack:
            node, depth = stack.pop(0)
            indent = ""
            for var in range(depth):
                indent += "\t"

            clade = treeDict[node]
            if noExtinct and clade.extinct:
                continue

            if hasattr(clade, "commonName") and clade.commonName != "":
                file.write(indent + clade.commonName + " (" + node + ")\n")
            else:
                file.write(indent + node + "\n")

            if max == -1 or depth < max:
                temp = []
                for var in clade.children:
                    temp.append((var, depth + 1))
                stack[0:0] = temp


# Goes through the default startup routine, importing the tree from the file and setting lastUpdated
def importTree():
    with open("tree.txt", "rb") as file:
        # treeDict = pickle.load(file)
        fileTuple = pickle.load(file)
        loadData(fileTuple)


# DO NOT DELETE THIS CODE
if __name__ == "__main__":
    importTree()
    #fullUpdate()

    #Put actual commands below here
    searchCommonNames("Ponginae",True)
    #printTaxonTree("South American native ungulate")
    #removeCommonName("Panini")
    #registerCommonName("Paracrocidura","Large-headed shrew")

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
