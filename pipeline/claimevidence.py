import pandas as pd
from bs4 import BeautifulSoup
import pickle
import pdb
import re
import string
import os
import glob
import json
import requests
import stanza
import time
import subprocess

# In[72]:

#stanza.download('en')

# {
#     "doc_id": number,               # The document's S2ORC ID.
#     "title": string,                # The title.
#     "abstract": string[],           # The abstract, written as a list of sentences.
#     "structured": boolean           # Indicator for whether this is a structured abstract.
# }
# {
#     "id": number,                   # An integer claim ID.
#     "claim": string,                # The text of the claim.
#     "evidence": {                   # The evidence for the claim.
#         [doc_id]: [                 # The rationales for a single document, keyed by S2ORC ID.
#             {
#                 "label": enum("SUPPORT" | "CONTRADICT"),
#                 "sentences": number[]
#             }
#         ]
#     },
#     "cited_doc_ids": number[]       # The documents cited by this claim's source citation sentence.
# }

# In[12]:

class ClaimEvidenceExtractor():
    
    def __init__(self, file, soup, test_csv):
        self.soup = soup
        self.document = test_csv
        self.s = re.split("_|\.",file)
        self.id = self.s[3]
        self.abstract = []
        self.nlp = stanza.Pipeline(lang='en', processors='tokenize')
        self.claims_start = 1500


    def remove_accents(self, text):
        text = re.sub('[âàäáãå]', 'a', text)
        text = re.sub('[êèëé]', 'e', text)
        text = re.sub('[îìïí]', 'i', text)
        text = re.sub('[ôòöóõø]', 'o', text)
        text = re.sub('[ûùüú]', 'u', text)
        text = re.sub('[ç]', 'c', text)
        text = re.sub('[ñ]', 'n', text)
        text = re.sub('[ÂÀÄÁÃ]', 'A', text)
        text = re.sub('[ÊÈËÉ]', 'E', text)
        text = re.sub('[ÎÌÏÍ]', 'I', text)
        text = re.sub('[ÔÒÖÓÕØ]', 'O', text)
        text = re.sub('[ÛÙÜÚ]', 'U', text)
        text = re.sub('[Ç]', 'C', text)
        text = re.sub('[Ñ]', 'N', text)
        return text

    def get_claims(self):
        data = pd.read_csv(self.document)
        paper_id = data.loc[:,'paper_id']
        try:
            index= [i for i in range(len(paper_id)) if paper_id[i]==self.id]
            #print(self.id,index)
            row = data.iloc[index[0], :]
        except:
            self.id = self.s[4]
            index= [i for i in range(len(paper_id)) if paper_id[i]==self.id]
            #print(self.id,index)
            row = data.iloc[index[0], :]
        self.doi = row['DOI_CR']
        self.title = row['title_CR']
        self.claim2 = row['claim2_abstract']
        self.claim2 = self.remove_accents(self.claim2)
        self.claim2 = re.split("\|",self.claim2)
        self.claim2_coded = row['coded_claim2']
        self.claim2_coded = self.remove_accents(self.claim2_coded)
        self.claim2_start = row['claim2_start']

        self.claim3a = row['claim3a_concretehyp']
        self.claim3a = self.remove_accents(self.claim3a)
        self.claim3a = re.split("\|",self.claim3a)
        self.claim3a_coded = row['coded_claim3a']
        self.claim3a_coded = self.remove_accents(self.claim3a_coded)
        self.claim3a_start = row['claim3a_start']

        self.claim3b = row['claim3b_testspec']
        self.claim3b = self.remove_accents(self.claim3b)
        self.claim3b = re.split("\|",self.claim3b)
        self.claim3b_coded = row['coded_claim3b']
        self.claim3b_coded = self.remove_accents(self.claim3b_coded)
        self.claim3b_start = row['claim3b_start']

        self.claim4 = row['claim4_inftest']
        self.claim4 = self.remove_accents(self.claim4)
        self.claim4 = re.split("\|",self.claim4)
        self.claim4_coded = row['coded_claim4']
        self.claim4_coded = self.remove_accents(self.claim4_coded)
        self.claim4_start = row['claim4_start']

        return
    
    def get_corpus(self):
        query = self.doi
        self.docid = 0
        self.abstract = []
        url = 'https://api.semanticscholar.org/v1/paper/'+str(query)
        r = requests.get(url)
        self.abstract = self.soup.find('abstract').get_text()
        doc = self.nlp(str(self.abstract))
        self.abstract = [sentence.text for sentence in doc.sentences]
        
        row = {"doc_id": int(self.docid), 'title':self.title, 'abstract':self.abstract, 'structured':'false'}
        if r.status_code != 200:
            return row
        data = r.json()
        data = pd.json_normalize(data)
        doi_api = data['doi']
        title_api = data['title']
        
        for i in range(0,len(doi_api)):
            doi_check = doi_api[i]
            if str(doi_check.lower()) == str(query.lower()):
                flag=0
                index = i
                doi = doi_api[i]
                title = title_api[i]
                break
            else:
                flag=1
        if flag==1:
            return row
        
        #print(data.loc[index,:])
        if 'corpusId' in data.columns:
            self.docid = data.loc[index,'corpusId']
        if not self.abstract:
            if 'abstract' in data.columns:
                self.abstract = data.loc[index,'abstract']
        row = {"doc_id": int(self.docid), 'title':self.title, 'abstract':self.abstract, 'structured':'false'}
        
        return row
        
    def getpara(self):
        self.para = self.soup.find_all('p')
        i=0
        sentences = 0
        all_output = []
        for p in self.para:
            i = i+1
            docid = self.docid+i
            p = p.get_text()
            doc = self.nlp(str(p))
            p = [sentence.text for sentence in doc.sentences]
            sentences = sentences + len(doc.sentences)
            output = {"doc_id": int(docid), 'title':self.title, 'abstract':p, 'structured':'false'}
            all_output.append(output)
        return all_output, sentences
        
    def getclaim(self, claim_id):
        final = []
        for k in range(1,5):
            if k == 1: c = self.claim2
            if k == 2: c = self.claim3a
            if k == 3: c = self.claim3b
            if k == 4: c = self.claim4
            #e  = [{"label": "enum(\"SUPPORT|CONTRADICT\")","sentences": "number[]"}]
            #evidence  = {"<doc_id>":e}
            #final = {"id":claim_id ,"claim": c ,"evidence":evidence ,"cited_doc_ids": "number[]"}
            
            if len(c)==1:
                claim_id = claim_id+1
                row = {"id":claim_id,"claim":c[0]}
                final.append(row)
            else:
                for i in c:
                    claim_id = claim_id+1
                    out = {"id":claim_id,"claim":i}
                    final.append(out)
        return final,claim_id
    
    def make_corpus(self):
        doc_ids = pd.DataFrame(columns = ['pdf', 'doc_id_start', 'doc_id_end', 'claims'])
        self.get_claims()
        row = self.get_corpus()
        output, self.sentences = self.getpara()
        k=0
        for i in output:
            if k==0:
                self.doc_start = i['doc_id']
            if k==(len(output)-1):
                self.doc_end = i['doc_id']
            k=k+1

        self.get_claims()
        final,self.claims_end = self.getclaim(self.claims_start)

        os.chdir(r"/home/rfn5089/pipeline-claimextraction/score_psu/pipeline/scifact/data/")
        f=open('corpus.jsonl','a',)
        for item in output:
            #print(item)
            json.dump(item,f, separators=(',', ':'))
            f.write('\n')
        f.close()

        os.chdir(r"/home/rfn5089/pipeline-claimextraction/score_psu/pipeline/scifact/data")
        f=open('claims_test.jsonl','w',)
        for item in final:
            #print(item)
            if isinstance(item, list):
                for j in item:
                    json.dump(j,f, separators=(',', ':'))
                    f.write('\n')
            else:
                json.dump(item,f, separators=(',', ':'))
                f.write('\n')
        f.close()

    def get_evidence(self,doc_id):
        dataset = []
        os.chdir(r'/home/rfn5089/pipeline-claimextraction/score_psu/pipeline/scifact/data/')
        with open('corpus.jsonl') as f:
            for item in f:
                data = json.loads(item)
                dataset.append(data)
        f.close()
        flag=0
        for item in dataset:
            if item['doc_id']==doc_id:
                evidence = item
                flag=1
                break
            else:
                pass
                flag=0
        if flag==1:
            return evidence['abstract']
        else:
            return []

    def get_results(self):
        dataset = []
        support_para = []
        contradict_para = []
        not_enough_info_para = []
        os.chdir(r'/home/rfn5089/pipeline-claimextraction/score_psu/pipeline/scifact/prediction/')
        with open('label_prediction.jsonl') as f:
            for item in f:
                data = json.loads(item)
                dataset.append(data)
        f.close()

        count = 0
        support = 0
        refute = 0
        for i in range(len(dataset)):
            entry = dataset[i]
            label_list = entry["labels"]
            for item in label_list:
                claim_id = entry["claim_id"]
                doc_id = item
                doc_id = int(doc_id)
                if claim_id>=self.claims_start and claim_id<=self.claims_end:
                    if doc_id>=int(self.doc_start) and doc_id<=int(self.doc_end):
                        l = label_list[item]
                    label = l["label"]
                    confidence = l["confidence"]
                    if confidence >=0.9:
                        if label=="SUPPORT":
                            support = support+1
                            support_para.append(self.get_evidence(doc_id))
                        if label=="CONTRADICT":
                            refute = refute+1
                            contradict_para.append(self.get_evidence(doc_id))
                        else:
                            not_enough_info_para.append(self.get_evidence(doc_id))
                count=count+1
        if self.sentences!=0:
            ratio = support/self.sentences
        else: 
            ratio = 0

        print(' Support: ', support, ' Refute: ', refute, ' Ratio: ', ratio)
        return support, refute, ratio, support_para, contradict_para, not_enough_info_para