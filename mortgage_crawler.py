import re
import mechanize
from mechanize import Browser
from bs4 import BeautifulSoup
import os
import errno
import pandas as pd
import time
import logging
import sys, traceback
#from multiprocessing import Pool
import numpy as np

def create_dir(directory):
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def setup(br):
    br.open("http://146.129.54.93:8193/search.asp?cabinet=opr")
    br.form = list(br.forms())[1]
    submit_response = br.submit(name=br.form.controls[0].name, label=br.form.controls[0].value)
    
def list_forms(browser):
    for form in browser.forms():
        print form
        
def list_controls(browser):
    for control in br.form.controls:
        print control

def get_parcel_document(parcel):
    directory = "parcel" + str(parcel)
    create_dir(directory)
    br = Browser()
    br.set_handle_robots(False)
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    setup(br)
    br.open("http://146.129.54.93:8193/search.asp?cabinet=opr")
    br.select_form("frmInput")
    parcel_from = br.form.find_control("txtCboTaxIDFr")
    parcel_to = br.form.find_control("txtCboTaxIDTo")
    parcel_from.value= str(parcel)
    parcel_to.value= str(parcel)
    response = br.submit()
    next_page = 2
    while True:
        text = response.read()
        parse_and_download(br, text, directory)
        link = has_next_page(br, text, next_page)
        if link:
            response = br.follow_link(link)
            next_page = next_page + 1
        else:
            break

def has_next_page(br, text, next_page):
    link = ''
    soup = BeautifulSoup(text)
    for ref in soup.find_all('a'):
        try:
            if ref.attrs["href"] == 'results.asp?pg=' + str(next_page):
                url = ref.attrs["href"]
                link = list(br.links(url=url))[0]
                break
        except Exception as e:
            continue
    return link

def parse_and_download(br, text, directory):
    soup = BeautifulSoup(text)
    rows = soup.find_all(valign='top')
    for i in range(2, len(rows)):
        current_row = rows[i]
        columns = current_row.find_all('td')
        docType = ""
        inst_num = columns[0].text
        # !!! Add Reference Instrument
        date = columns[2].text
        name = columns[4].text + '~' + columns[6].text
        image_col = columns[9]
        try:
            if image_col.find('img'):
                docType = docType + columns[3].text
                url = image_col.find('a').attrs["href"]
                link = list(br.links(url=url))[0]
                file_name = docType + '-' + date + '-' + name + '-' + inst_num
                file_name = file_name.replace("/", ".")
                retrieve_tiff(directory + '/' + file_name, br, link)
                #br.open(response.geturl()) # so we can go back
            else:
                # we need to go down another level to find the docs
                inst_col = columns[0]
                url = inst_col.find('a').attrs["href"]
                link = list(br.links(url=url))[0]
                get_doc_files(br, link, directory, docType, date, name, inst_num)
        except Exception as e:
            file_name = docType + '-' + date + '-' + name + '-' + inst_num
            with open(directory + '/' + file_name.replace("/", "."), 'a') as f:
                f.write(str(e))
                traceback.print_exc(file=f)

def find_doc_index(rows):
    for i in range(len(rows)):
        columns = rows[i].find_all('td')
        try:
            if columns[1].text == 'Referenced Instrument':
                return i+1
        except Exception:
            continue
def find_doc_row(rows, name):
    for i in range(len(rows)):
        columns = rows[i].find_all('td')
        try:
            if columns[0].text == name:
                return i
        except Exception:
            continue
def get_doc_files(br, link, directory, docType, date, name, inst_num, count=0):
    if count == 4:
        # this means that there's a cyclic loop
        return
    doc_detail = br.follow_link(link)
    text = doc_detail.read()
    soup = BeautifulSoup(text)
    rows = soup.find_all(valign='top')
    doc_index = find_doc_row(rows, 'Document Type:')
    doc_value = rows[doc_index].find_all('td')[1]
    docType = docType + doc_value.text + '|'
    image_index = find_doc_row(rows, 'Image:')
    image_value = rows[image_index].find_all('td')[1]
    if image_value.find('a'):
        # if there's a link to download
        url = image_value.find('a').attrs["href"]
        link = list(br.links(url=url))[0]
        file_name = docType + '-' + date + '-' + name + '-' + inst_num
        file_name = file_name.replace("/", ".")
        retrieve_tiff(directory + '/' + file_name, br, link)
    else:
        try:
            for i in range(find_doc_index(rows), len(rows)):
                columns = rows[i].find_all('td')
                inst_col = columns[1]
                url = inst_col.find('a').attrs["href"]
                link = list(br.links(url=url))[0]
                get_doc_files(br, link, directory, docType, date, name, inst_num, count + 1)
        except Exception as e:
            file_name = docType + '-' + date + '-' + name + '-' + inst_num
            with open(directory + '/' + file_name.replace("/", "."), 'a') as f:
                f.write(text)
                f.write(str(link))
                f.write(str(e))
                traceback.print_exc(file=f)
    br.back()

def retrieve_tiff(file_name, br, link):
    br.follow_link(link)
    br.form = list(br.forms())[1] # Retrieve as TIFF
    br.submit(name=br.form.controls[3].name, label=br.form.controls[3].value)
    link = list(br.links(text_regex=re.compile("TIFF")))[0]
    br.retrieve("http://146.129.54.93:8193/" + link.url, file_name)
    br.back()
    br.back()

def main():
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    parcels = np.load('parcels.npy')
    #parcels = pd.read_csv('parcels.csv', low_memory=False, header=None)
    #parcels = parcels[starting*count: starting*count + count].reset_index(drop=True)
    #start = time.time()
    directory = 'parcel_documents'
    os.chdir(directory)
    logging.basicConfig(filename='parcel_parsing.log')
    for i in range(start, end):
        print i
        try:
            get_parcel_document(parcels[i])
        except Exception as e:
            print parcel[i]
            print e
            traceback.print_exc()
            continue
    os.chdir('..')
    #end = time.time()
    #print(end-start)

if __name__ == "__main__":
    main()
