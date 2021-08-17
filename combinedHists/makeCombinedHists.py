#!/usr/bin/env python2

import collections
import glob
import re
import os
import copy
import numpy as np
import datetime
import string
import shutil
import subprocess
import pickle
import math
import json
import ast
import sys
import csv

import ROOT
from ROOT import gPad, gStyle, gROOT

class Parameter:
    name = ""
    label = ""
    cut = 0
    veto = 0
    minDraw = 0
    maxDraw = 0
    def __init__(self, n, l, c, v, minDraw, maxDraw):
        self.name = n
        self.label = l
        self.cut = c
        self.veto = v
        self.minDraw = minDraw
        self.maxDraw = maxDraw
parameters = [
    Parameter("Xpos", "#Deltax [#mum]", 5, 200, -30, 30 ), \
    Parameter("Ypos", "#Deltay [#mum]", 10, 200, -30, 30 ), \
    Parameter("Zpos", "#Deltaz [#mum]", 15, 200, -30, 30 ), \
    Parameter("Xrot", "#Delta#theta_{x} [#murad]", 30, 200, -50, 50 ), \
    Parameter("Yrot", "#Delta#theta_{y} [#murad]", 30, 200, -50, 50 ), \
    Parameter("Zrot", "#Delta#theta_{z} [#murad]", 30, 200, -50, 50 )
    ]
parameters_e = [
    Parameter("Xpos", "#sigma_{#Deltax} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Ypos", "#sigma_{#Deltay} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Zpos", "#sigma_{#Deltaz} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Xrot", "#sigma_{#Delta#theta_{x}} [#murad]", 0, 10, -50, 50 ), \
    Parameter("Yrot", "#sigma_{#Delta#theta_{y}} [#murad]", 0, 10, -50, 50 ), \
    Parameter("Zrot", "#sigma_{#Delta#theta_{z}} [#murad]", 0, 10, -50, 50 )
    ]
parameters_sig = [
    Parameter("Xpos", "#Deltax/#sigma_{#Deltax}", 2.5, 0, -30, 30 ), \
    Parameter("Ypos", "#Deltay/#sigma_{#Deltay}", 2.5, 0, -30, 30 ), \
    Parameter("Zpos", "#Deltaz/#sigma_{#Deltaz}", 2.5, 0, -30, 30 ), \
    Parameter("Xrot", "#Delta#theta_{x}/#sigma_{#Delta#theta_{x}}", 2.5, 0, -50, 50 ), \
    Parameter("Yrot", "#Delta#theta_{y}/#sigma_{#Delta#theta_{y}}", 2.5, 0, -50, 50 ), \
    Parameter("Zrot", "#Delta#theta_{z}/#sigma_{#Delta#theta_{z}}", 2.5, 0, -50, 50 )
    ]
parDict = collections.OrderedDict( (p.name, p) for p in parameters )
objects = [
    ("Disk-1", ROOT.kBlack),
    ("Disk-2", ROOT.kCyan),
    ("Disk-3", ROOT.kBlue),
    ("Disk1", ROOT.kBlack+3),
    ("Disk2", ROOT.kCyan+2),
    ("Disk3", ROOT.kBlue+2),
    ("Layer1", ROOT.kRed),
    ("Layer2", ROOT.kGreen+2),
    ("Layer3", ROOT.kMagenta),
    ("Layer4", ROOT.kOrange),
]

#  ~plotDir = "./plots/PR_starting_2018B_mid2018D"
plotDir = "./plots/PR_starting_2018B_diffHits/500Hits"
#  ~plotDir = "./plots/317182"
def save(name, folder="plots", endings=[".pdf"]):
    if not os.path.exists(folder):
        os.makedirs(folder)
    for ending in endings:
        ROOT.gPad.GetCanvas().SaveAs(os.path.join(folder,name+ending))

def runFromFilename(filename):
    m = re.match(".*run(\d+)/", filename)
    if m:
        return int(m.group(1))
    else:
        print "Could not find run number for file", filename
        return 0

def sortedDict(d):
    return collections.OrderedDict(sorted(d.items(), key=lambda t: t[0]))

def getFromFile(filename, objectname):
    f = ROOT.TFile(filename)
    if f.GetSize()<5000: # DQM files sometimes are empty
        return None
    h = f.Get(objectname)
    h = ROOT.gROOT.CloneObject(h)
    return h

def randomName():
    """
    Generate a random string. This function is useful to give ROOT objects
    different names to avoid overwriting.
    """
    from random import randint
    from sys import maxint
    return "%x"%(randint(0, maxint))

def mergeOverflow(h,includeUnderflow):
    N=h.GetNbinsX()
    entries=h.GetEntries()
    #overflow
    cont=h.GetBinContent(N)+h.GetBinContent(N+1)
    err2=np.sqrt(h.GetBinError(N)**2+h.GetBinError(N+1)**2)
    #set content+error of last bin
    h.SetBinContent(N,cont)
    h.SetBinError(N,np.sqrt(err2))
    #clear overflow
    h.SetBinContent(N+1,0)
    h.SetBinError(N+1,0)
    #underflow
    if includeUnderflow:
        cont=h.GetBinContent(0)+h.GetBinContent(1)
        err2=np.sqrt(h.GetBinError(0)**2+h.GetBinError(1)**2)
        #set content+error of first bin
        h.SetBinContent(1,cont)
        h.SetBinError(1,np.sqrt(err2))
        #clear overflow
        h.SetBinContent(0,0)
        h.SetBinError(0,0)
        #restore correct number of entries
        h.SetEntries(entries)
    return h

#  ~def getInputHists(searchPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/output/HG_run*/DQM*.root"):
#  ~def getInputHists(searchPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/2018B_PRstartingGeometry_iterativ_diffHits/50Hits/HG_run*/DQM*.root"):
def getInputHists(searchPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/2018B_PRstartingGeometry_iterativ_diffHits/500Hits/HG_run*/DQM*.root"):
    hists = {}
    for filename in glob.glob(searchPath):
        runNr = runFromFilename(filename)
        #  ~if runNr!=317182: continue
        print runNr
        path_in_file="DQMData/Run "+str(runNr)+"/AlCaReco/Run summary/SiPixelAli/"
        newHists = {}
        if runNr<=318877:
        #  ~if True:
            for p in parameters:
                for structure in objects:
                    histName=p.name+"_HG_"+structure[0]
                    h = getFromFile(filename, path_in_file+histName)
                    if h:
                        newHists[histName] = h
            if newHists: hists[runNr] = newHists
    return sortedDict(hists)
    
def getCombinedHist(inputHists, minRun=-1):
    inputHists = sortedDict(dict((key,value) for key, value in inputHists.iteritems() if key >= minRun))
    hists = {}
    hists_e = {}
    hists_sig = {}
    isbpix = False
    islayer4 = False
    for iRun, (runNr, hmap) in enumerate(inputHists.iteritems()):
        print runNr
        for hname, h in hmap.iteritems():
            isbpix = hname.find("Layer")!=-1
            islayer4 = hname.find("Layer4")!=-1
            
            limit = 100
            limit_e = 30
            if isbpix==False and hname.find("Xrot")!=-1: 
                limit = 600
                limit_e = 400
            elif isbpix==False and hname.find("Zrot")!=-1: 
                limit = 600
                limit_e = 200
            elif hname.find("Yrot")!=-1: 
                limit=1000
                limit_e = 400
            
            hdefault = ROOT.TH1F("",";Movement;Entries",100,-limit,limit)
            hdefault_e = ROOT.TH1F("",";Error;Entries",100,0,limit_e)
            hdefault_sig = ROOT.TH1F("",";Error;Entries",100,-20,20)
            if isbpix==False:
                if hname not in hists:
                    hists[hname] = hdefault.Clone()
                    hists_e[hname] = hdefault_e.Clone()
                    hists_sig[hname] = hdefault_sig.Clone()
                if h.GetBinContent(1)==0:
                   failed = True 
                   continue  #alignment did not finish successfull
                for bin in range(1,h.GetNbinsX()+1):
                    c = h.GetBinContent(bin)
                    e = h.GetBinError(bin)
                    hists[hname].Fill(c)
                    hists_e[hname].Fill(e)
                    hists_sig[hname].Fill(c/e if e>0 else 0)
            else:
                if hname+"_out" not in hists:
                    hists[hname+"_out"] = hdefault.Clone()
                    hists_e[hname+"_out"] = hdefault_e.Clone()
                    hists_sig[hname+"_out"] = hdefault_sig.Clone()
                if hname+"_in" not in hists:
                    hists[hname+"_in"] = hdefault.Clone()
                    hists_e[hname+"_in"] = hdefault_e.Clone()
                    hists_sig[hname+"_in"] = hdefault_sig.Clone()
                for bin in range(1,h.GetNbinsX()+1):
                    c = h.GetBinContent(bin)
                    e = h.GetBinError(bin)
                    i = 0
                    if islayer4: i=1
                    if bin%2==i:
                        hists[hname+"_out"].Fill(c)
                        hists_e[hname+"_out"].Fill(e)
                        hists_sig[hname+"_out"].Fill(c/e if e>0 else 0)
                    else:
                        hists[hname+"_in"].Fill(c)
                        hists_e[hname+"_in"].Fill(e)
                        hists_sig[hname+"_in"].Fill(c/e if e>0 else 0)
    
    #  ~hists["Xpos_HG_Layer1_out"].SaveAs("out1.root")
    #  ~hists["Xpos_HG_Layer4_in"].SaveAs("in4.root")
    #  ~hists["Xpos_HG_Layer3_out"].SaveAs("out3.root")
    #  ~hists["Xpos_HG_Layer3_in"].SaveAs("in3.root")
    return hists,hists_e,hists_sig

def drawCombinedHists(hmaps):
    for ih,hmap in enumerate(hmaps):
        objectDict = {}
        for structure in objects:
            objectDict[structure[0]] = structure[1]
        
        paramDict = {}
        parameters_temp = parameters
        if ih==1 : parameters_temp=parameters_e
        elif ih==2 : parameters_temp=parameters_sig
        for param in parameters_temp:
            paramDict[param.name] = param
        if not hmap: return
        gROOT.SetBatch(True)
        line = ROOT.TLine()
        line.SetLineStyle(2)
        line_e = ROOT.TLine()
        line_e.SetLineStyle(2)
        line_e.SetLineColor(ROOT.kRed)
        leg = ROOT.TLegend(.61, .78, .969, .929)
        leg.SetNColumns(2)
        leg.SetBorderSize(1)
        leg.SetLineWidth(2)
        #  ~leg.AddEntry(line, "Threshold", "l")
        gStyle.SetFrameLineWidth(2)
        c = ROOT.TCanvas(randomName(),"",700,600)
        hists = {}
        isbpix = False
        for ig,(name,hist) in enumerate(hmap.iteritems()):
            print name
            isbpix = name.find("Layer")!=-1
            structure = name.split("_")[2]
            param = name.split("_")[0]
            hist = mergeOverflow(hist,True)
            hists[ig] = hist.Clone()
            hists[ig].SetStats(0)
            hists[ig].SetTitle(";{};{}".format(paramDict[param].label,"Entries"))
            gPad.SetLeftMargin(100)
            hists[ig].SetMarkerColor(objectDict[structure])
            hists[ig].SetLineColor(objectDict[structure])
            hists[ig].SetLineWidth(2)
            hists[ig].SetMaximum(1.3*hists[ig].GetMaximum())
            hists[ig].Draw("hist")
            hists[ig].GetYaxis().SetTitleOffset(0.95)
            gStyle.SetHistTopMargin(0.)
            if ih==0 or ih==2:
                line.DrawLine(-paramDict[param].cut, 0, -paramDict[param].cut,hists[ig].GetMaximum())
                line.DrawLine(+paramDict[param].cut, 0, +paramDict[param].cut,hists[ig].GetMaximum())
            if ih==0 or ih==1:
                if ih==0: line_e.DrawLine(-paramDict[param].veto, 0, -paramDict[param].veto,hists[ig].GetMaximum())
                line_e.DrawLine(+paramDict[param].veto, 0, +paramDict[param].veto,hists[ig].GetMaximum())
            gPad.RedrawAxis()
            text = ROOT.TLatex()
            text.SetTextSize(0.04)
            text.DrawLatexNDC(.1, .91, "#scale[1.2]{#font[61]{CMS}} #font[52]{Private Work}")
            text.DrawLatexNDC(.6, .91, "2018 pp collisions")
            text.DrawLatexNDC(.59, .645, structure+name.split("_")[3] if isbpix else structure)
            if ih!=1:
                text.DrawLatexNDC(.55, .445, "{:3.0f} % above update threshold".format(100*(hists[ig].Integral(0,hists[ig].GetXaxis().FindBin(-paramDict[param].cut)-1)+hists[ig].Integral(hists[ig].GetXaxis().FindBin(+paramDict[param].cut),hists[ig].GetNbinsX()+1))/hists[ig].GetEntries()))
            if (ih==0 and paramDict[param].veto<hists[ig].GetXaxis().GetXmax()):
                text.DrawLatexNDC(.55, .345, "{:3.0f} % above veto threshold".format(100*(hists[ig].Integral(0,hists[ig].GetXaxis().FindBin(-paramDict[param].veto)-1)+hists[ig].Integral(hists[ig].GetXaxis().FindBin(+paramDict[param].veto),hists[ig].GetNbinsX()+1))/hists[ig].GetEntries()))
            elif (ih==1 and paramDict[param].veto<hists[ig].GetXaxis().GetXmax()):
                text.DrawLatexNDC(.55, .345, "{:3.0f} % above veto threshold".format(100*hists[ig].Integral(hists[ig].GetXaxis().FindBin(+paramDict[param].veto),hists[ig].GetNbinsX()+1)/hists[ig].GetEntries()))
            if ih==0 : save(name, plotDir+"/movements", endings=[".pdf",".root"])
            elif ih==1 : save(name, plotDir+"/errors", endings=[".pdf",".root"])
            else : save(name, plotDir+"/significance", endings=[".pdf",".root"])
            c.Clear()
            leg.Clear()

if __name__ == "__main__":
    inputHists = getInputHists()
    
    combinedHists = getCombinedHist(inputHists)

    drawCombinedHists(combinedHists)

