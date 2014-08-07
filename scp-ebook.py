#!/usr/bin/env python3

from urllib.request import urlopen
from urllib.error import HTTPError
from bs4 import BeautifulSoup
from lxml import etree, html
import re
import os
import shutil
import copy
import time
import requests


class Page():

    """placeholder docstring"""

    #titles for scp articles
    scp_index = {}

    def __init__(self, url=None):
        self.url = url
        self.tags = []
        self.author = None
        if url is not None:
            self.scrape()
            self.cook()

    def scrape(self):
        '''Scrape the contents of the given url.'''
        def cached(path, scrape_func):
            if os.path.isfile(path):
                with open(path, "r") as F:
                    return F.read()
            else:
                data = scrape_func()
                with open(path, "w") as F:
                    F.write(data)
                return data

        def scrape_page_body():
            print("downloading: \t" + self.url)
            try:
                soup = BeautifulSoup(urlopen(self.url))
            except HTTPError:
                return None
            return str(soup)

        def scrape_history():
            print("d-ing history: \t" + self.url)
            pageid = re.search("pageId = ([^;]*);", self.soup).group(1)
            headers = {"Content-Type": "application/x-www-form-urlencoded;",
                       "Cookie": "wikidot_token7=123456;"}
            payload = ("page=1&perpage=1000&page_id=" + pageid +
                       "&moduleName=history%2FPageRevisionListModule"
                       "&wikidot_token7=123456")
            data = requests.post("http://www.scp-wiki.net/ajax-module-"
                                 "connector.php", data=payload,
                                 headers=headers).json()["body"]
            return data
        cfile = re.search("/[^/]*$", self.url).group()[1:]
        if cfile == "":
            self.soup = None
            return
        self.soup = cached("data/" + cfile, scrape_page_body)
        self.history = cached("data/history/" + cfile, scrape_history)

    def cook(self):
        '''Cook the soup, retrieve title, data, and tags'''
        if not self.soup:
            self.title = None
            self.data = None
            return
        soup = BeautifulSoup(self.soup)
        # meta
        self.tags = [a.string for a in soup.select("div.page-tags a")]
        self.author = BeautifulSoup(self.history
                                    ).select("tr")[-1].select("td")[-3].text
        # title
        if soup.select("#page-title"):
            title = soup.select("#page-title")[0].text.strip()
        else:
            title = ""
        # because 001 proposals don't have their own tag,
        # it's easier to check if the page is a mainlist skip
        # by regexping its url instead of looking at tags
        if "scp" in self.tags and re.match(".*scp-[0-9]{3,4}$", self.url):
            if Page.scp_index == {}:
                index_urls = ["http://www.scp-wiki.net/scp-series",
                              "http://www.scp-wiki.net/scp-series-2",
                              "http://www.scp-wiki.net/scp-series-3"]
                for u in index_urls:
                    s = BeautifulSoup(Page(u).soup)
                    entries = s.select("ul li")
                    for e in entries:
                        if re.match(".*>SCP-[0-9]*<.*", str(e)):
                            i = e.text.split(" - ")
                            Page.scp_index[i[0]] = i[1]
            title = title + ": " + Page.scp_index["SCP-" + title[4:]]
        self.title = title
        # body
        if not soup.select("#page-content"):
            self.data = None
            return
        data = soup.select("#page-content")[0]
        [i.decompose() for i in data.select("table") if i.select("img")]
        garbage = ["div.page-rate-widget-box", "div.scp-image-block", "img"]
        [k.decompose() for e in garbage for k in data.select(e)]
        # tables
        # tab-views
        for i in data.select("div.yui-navset"):
            wraper = soup.new_tag("div", **{"class": "tabview"})
            titles = [a.text for a in i.select("ul.yui-nav em")]
            tabs = i.select("div.yui-content > div")
            for k in tabs:
                k.attrs = {"class": "tabview-tab"}
                tab_title = soup.new_tag("div", **{"class": "tab-title"})
                tab_title.string = titles[tabs.index(k)]
                k.insert(0, tab_title)
                wraper.append(k)
            i.replace_with(wraper)
        # footnotes
        for i in data.select("sup.footnoteref"):
            i.string = i.a.string
        for i in data.select("div.footnote-footer"):
            i["class"] = "footnote"
            del(i["id"])
            i.string = "".join([k for k in i.strings])
        # collapsibles
        for i in data.select("div.collapsible-block"):
            link_text = i.select("a.collapsible-block-link")[0].text
            content = i.select("div.collapsible-block-content")[0]
            content["class"] = "collaps-content"
            col = soup.new_tag("div", **{"class": "collapsible"})
            content = content.wrap(col)
            col_title = soup.new_tag("div", **{"class": "collaps-title"})
            col_title.string = link_text
            content.div.insert_before(col_title)
            i.replace_with(content)
        # links
        for i in data.select("a"):
            del(i["href"])
            i.name = "span"
            i["class"] = "link"
        #quote boxes
        for i in data.select("blockquote"):
            i.name = "div"
            i["class"] = "quote"
        #add title to the page
        if "scp" in self.tags:
            data = "<p class='scp-title'>" + self.title + "</p>" + str(data)
        else:
            data = "<p class='tale-title'>" + self.title + "</p>" + str(data)
        self.data = data

    def list_children(self):
        def links(self):
            links = []
            soup = BeautifulSoup(self.soup)
            for a in soup.select("#page-content a"):
                if not a.has_attr("href") or a["href"][0] != "/":
                    # this whole section up to 'continue' is for
                    # debug purposes only, can be deleted in the final version
                    if a.has_attr("href"):
                        if (a["href"] != "javascript:;" and a["href"][0] != "#"
                            and re.search("scp-wiki", a["href"])
                                and not re.search("local--files", a["href"])):
                            print("bad link on page " + self.url + "\t(" +
                                  a["href"] + ")")
                    continue
                url = "http://www.scp-wiki.net" + a["href"]
                url = url.rstrip("|")
                if url in links:
                    continue
                links.append(url)
            return links

        if not any(i in self.tags for i in ["scp", "hub", "splash"]):
            return []
        lpages = []
        for url in links(self):
            p = Page(url)
            if p.soup and p.data:
                lpages.append(p)
        if any(i in self.tags for i in ["scp", "splash"]):
            mpages = [i for i in lpages if
                      any(k in i.tags for k in ["supplement", "splash"])]
            return mpages
        if "hub" in self.tags and any(i in self.tags
                                      for i in ["tale", "goi2014"]):
            mpages = [i for i in lpages if any(k in i.tags for k in
                      ["tale", "goi-format", "goi2014"])]

            def backlinks(page, child):
                if page.url in links(child):
                    return True
                soup = BeautifulSoup(child.soup)
                if soup.select("#breadcrumbs a"):
                    crumb = soup.select("#breadcrumbs a")[-1]
                    crumb = "http://www.scp-wiki.net" + crumb["href"]
                    if self.url == crumb:
                        return True
                return False
            if any(backlinks(self, p) for p in mpages):
                return [p for p in mpages if backlinks(self, p)]
            else:
                return mpages


class Epub():

    """"""

    def __init__(self, title):
        self.title = title
        #change to a proper temp dir later on
        self.dir = os.getcwd() + "/ebook/"
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)
        os.mkdir(self.dir)
        self.templates = {}
        for i in os.listdir("templates"):
            self.templates[i.split(".")[0]] = etree.parse(os.getcwd() +
                                                          "/templates/" + i)
        self.allpages = []
        #pre-building toc
        toc = self.templates["toc"]
        for i in toc.getroot().iter():
            if i.tag.endswith("text"):
                i.text = title
        self.toc = toc

    def add_page(self, page, node=None):
        #print(page.title)
        if page.title in [i["title"] for i in self.allpages]:
            return
        n = len(self.allpages)
        uid = "page_" + str(n).zfill(4)
        epub_page = copy.deepcopy(self.templates["page"])
        for i in epub_page.getroot().iter():
            if i.tag.endswith("title"):
                i.text = page.title
            elif i.tag.endswith("body"):
                body = html.fromstring(page.data)
                i.append(body)
        epub_page.write(self.dir + uid + ".xhtml")
        self.allpages.append({"title": page.title, "id": uid,
                              "author": page.author, "url": page.url})

        def add_to_toc(node, page, uid):
            if node is None:
                node = self.toc.getroot().find("{http://www.daisy.org/z3986/"
                                               "2005/ncx/}navMap")
            navpoint = etree.SubElement(node, "navPoint", id=uid,
                                        playOrder=str(len(self.allpages)))
            navlabel = etree.SubElement(navpoint, "navLabel")
            etree.SubElement(navlabel, "text").text = page.title
            etree.SubElement(navpoint, "content", src=uid + ".xhtml")
            return navpoint
        new_node = add_to_toc(node, page, uid)
        [self.add_page(i, new_node) for i in page.list_children()]

    def save(self, file):
        self.toc.write(self.dir + "toc.ncx", xml_declaration=True,
                       encoding="utf-8", pretty_print=True)
        #building the spine
        spine = self.templates["content"]
        self.allpages.sort(key=lambda k: k["id"])
        for i in spine.getroot().iter():
            if i.tag.endswith("meta"):
                if ("property" in i.attrib and
                        i.attrib["property"] == "dcterms:modified"):
                    i.text = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            elif i.tag.endswith("title"):
                i.text = self.title
            elif i.tag.endswith("manifest"):
                for k in self.allpages:
                    etree.SubElement(i, "item",
                                     href=k["id"] + ".xhtml", id=k["title"],
                                     **{"media-type":
                                        "application/xhtml+xml"})
            elif i.tag.endswith("spine"):
                for k in self.allpages:
                    etree.SubElement(i, "itemref", idref=k["title"])
        spine.write(self.dir + "content.opf", xml_declaration=True,
                    encoding="utf-8", pretty_print=True)
        #other necessary files
        container = self.templates["container"]
        os.mkdir(self.dir + "META-INF/")
        container.write(self.dir + "META-INF/container.xml",
                        xml_declaration=True, encoding="utf-8",
                        pretty_print=True)
        with open(self.dir + "mimetype", "w") as F:
            F.write("application/epub+zip")
        shutil.copy("stylesheet.css", self.dir)
        shutil.copy("cover.png", self.dir)
        shutil.make_archive("test.epub", "zip", self.dir)
        shutil.move("test.epub.zip", "test.epub")


def yield_pages():
    def urls_by_tag(tag):
        p = Page("http://www.scp-wiki.net/system:page-tags/tag/" + tag)
        soup = BeautifulSoup(p.soup)
        urls = ["http://www.scp-wiki.net" + a["href"] for a in
                soup.select("""div.pages-list
                            div.pages-list-item div.title a""")]
        return urls

    def natural_key(s):
        re_natural = re.compile('[0-9]+|[^0-9]+')
        return [(1, int(c)) if c.isdigit() else (0, c.lower()) for c
                in re_natural.findall(s)] + [s]
    # skips
    scp_main = [i for i in urls_by_tag("scp") if re.match(".*scp-[0-9]*$", i)]
    scp_main = sorted(scp_main, key=natural_key)
    scp_blocks = [[i for i in scp_main if (int(i.split("-")[-1]) // 100 == n)]
                  for n in range(30)]
    for b in scp_blocks[:1]:
        b_name = "SCP Database/Chapter " + str(scp_blocks.index(b) + 1)
        for url in b:
            p = Page(url)
            p.chapter = b_name
            yield p
    return

    def quick_yield(tags, chapter_name):
        L = [urls_by_tag(i) for i in tags if type(i) == str]
        for i in [i for i in tags if type(i) == list]:
            a = [x for k in i for x in urls_by_tag(k)]
            L.append(a)
        for url in [i for i in L[0] if all(i in t for t in L)]:
            p = Page(url)
            p.chapter = chapter_name
            yield p
    #yield from quick_yield(["joke", "scp"], "SCP Database/Joke Articles")
    #yield from quick_yield(["explained", "scp"],
    #                       "SCP Database/Explained Phenomena")
    yield from quick_yield(["hub", ["tale", "goi2014"]], "Canons and Series")
    #yield from quick_yield(["tale"], "Assorted Tales")


def main():
    book = Epub("SCP Foundation")
    pages_intro = []
    pages_outro = []
    for f in [f for f in sorted(os.listdir(os.getcwd() + "/pages"))
              if os.path.isfile(os.path.join(os.getcwd() + "/pages", f))]:
                p = Page()
                p.title = f[3:-6]
                with open(os.path.join(os.getcwd() + "/pages", f)) as F:
                    p.data = F.read()
                if f[0] == "0":
                    pages_intro.append(p)
                else:
                    pages_outro.append(p)
    [book.add_page(p) for p in pages_intro]
    for i in yield_pages():
        c_up = None

        def node_with_text(text):
            for k in book.toc.iter("navPoint"):
                if text == k.find("navLabel").find("text").text:
                    return k
        for c in i.chapter.split("/"):
            if not c in [i["title"] for i in book.allpages]:
                print(c)
                p = Page()
                p.title = c
                p.data = "<div></div>"
                book.add_page(p, node_with_text(c_up))
            c_up = c
        #print(i.title)
        book.add_page(i, node_with_text(c_up))
    #[book.add_page(p) for p in pages_outro]
    attrib = Page()
    attrib.title = "Acknowledgments and Attributions"
    attrib.data = ""
    for i in sorted(book.allpages, key=lambda k: k["id"]):
        if i["author"] is not None:
            attrib.data += "<p><strong>" + i["title"] + "</strong> (" +\
                           i["url"] + ") was written by <strong>" +\
                           i["author"] + "</strong>."
    book.add_page(attrib)
    book.save("test.epub")

main()
