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

# class defining the plotting parameters for different measures (e.g. movement) and different variables (e.g. Xpos)
# the colors for different subdetectors are defined as well
class Parameter:
    name = ""     # variable name
    label = ""    # axis label
    cut = 0       # threshold value
    veto = 0      # veto value
    minDraw = 0   # x-axis lower limit
    maxDraw = 0   # x-axis upper limit
    def __init__(self, n, l, c, v, minDraw, maxDraw):
        self.name = n
        self.label = l
        self.cut = c
        self.veto = v
        self.minDraw = minDraw
        self.maxDraw = maxDraw
parameters = [    # movements
    Parameter("Xpos", "#Deltax [#mum]", 5, 200, -30, 30 ), \
    Parameter("Ypos", "#Deltay [#mum]", 10, 200, -30, 30 ), \
    Parameter("Zpos", "#Deltaz [#mum]", 15, 200, -30, 30 ), \
    Parameter("Xrot", "#Delta#theta_{x} [#murad]", 30, 200, -50, 50 ), \
    Parameter("Yrot", "#Delta#theta_{y} [#murad]", 30, 200, -50, 50 ), \
    Parameter("Zrot", "#Delta#theta_{z} [#murad]", 30, 200, -50, 50 )
    ]
parameters_e = [  # errors
    Parameter("Xpos", "#sigma_{#Deltax} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Ypos", "#sigma_{#Deltay} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Zpos", "#sigma_{#Deltaz} [#mum]", 0, 10, -30, 30 ), \
    Parameter("Xrot", "#sigma_{#Delta#theta_{x}} [#murad]", 0, 10, -50, 50 ), \
    Parameter("Yrot", "#sigma_{#Delta#theta_{y}} [#murad]", 0, 10, -50, 50 ), \
    Parameter("Zrot", "#sigma_{#Delta#theta_{z}} [#murad]", 0, 10, -50, 50 )
    ]
parameters_sig = [ # significances
    Parameter("Xpos", "#Deltax/#sigma_{#Deltax}", 2.5, 0, -30, 30 ), \
    Parameter("Ypos", "#Deltay/#sigma_{#Deltay}", 2.5, 0, -30, 30 ), \
    Parameter("Zpos", "#Deltaz/#sigma_{#Deltaz}", 2.5, 0, -30, 30 ), \
    Parameter("Xrot", "#Delta#theta_{x}/#sigma_{#Delta#theta_{x}}", 2.5, 0, -50, 50 ), \
    Parameter("Yrot", "#Delta#theta_{y}/#sigma_{#Delta#theta_{y}}", 2.5, 0, -50, 50 ), \
    Parameter("Zrot", "#Delta#theta_{z}/#sigma_{#Delta#theta_{z}}", 2.5, 0, -50, 50 )
    ]
parDict = collections.OrderedDict( (p.name, p) for p in parameters )
objects = [    # define color for different subdetectors
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

# method to save plots and create saving path if not exists
def save(name, folder="plots", endings=[".pdf"]):
    if not os.path.exists(folder):
        os.makedirs(folder)
    for ending in endings:
        ROOT.gPad.GetCanvas().SaveAs(os.path.join(folder,name+ending))

# method to get the runNo from a filename
def runFromFilename(filename):
    m = re.match(".*run(\d+)/", filename)
    if m:
        return int(m.group(1))
    else:
        print "Could not find run number for file", filename
        return 0

# method to sort dictionary by key value
def sortedDict(d):
    return collections.OrderedDict(sorted(d.items(), key=lambda t: t[0]))

# method to change the axis of a 2D dictionary    
def changeAxisDict(d):
    tempDict = {}
    for item_x in d.itervalues().next():
        tempDict[item_x] = {}
    
    for item_y in d:
        for item_x in d[item_y]:
            tempDict[item_x][item_y] = d[item_y][item_x]
    
    return tempDict

# method to get root object from DQM file
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

# method to merge overflow (and underflow) of a given histogram
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

# method to get histograms from list a given search path (returns multiple histograms per run and hit option)
def getInputHists(searchPath):
    hits = ["50Hits","100Hits","300Hits","500Hits"]
    hists = {}
    for hitOption in hits:      # loop over different hit options
        hists[hitOption] = {}
        for filename in glob.glob(searchPath.format(hitOption)):
            runNr = runFromFilename(filename)
            print runNr
            path_in_file="DQMData/Run "+str(runNr)+"/AlCaReco/Run summary/SiPixelAli/"
            newHists = {}
            if runNr<=318877:       # currently used for debugging, should be changed to true if all runs in search path should be considered
            #  ~if True:
                for p in parameters:
                    for structure in objects:
                        histName=p.name+"_HG_"+structure[0]
                        h = getFromFile(filename, path_in_file+histName)
                        if h:
                            newHists[histName] = h
                if newHists: hists[hitOption][runNr] = newHists
    #  ~return sortedDict(hists)
    return hists
    
# method to produce one histogram for each combination of hitnumber, variable and subdetector from multiple runs
def getCombinedHist(inputHists, minRun=-1):
    hists = {}
    hists_e = {}
    hists_sig = {}
    for item in inputHists:     # loop over hitnumbers
        hists[item] = {}
        hists_e[item] = {}
        hists_sig[item] = {}
        inputHists_temp = sortedDict(dict((key,value) for key, value in inputHists[item].iteritems() if key >= minRun))
        isbpix = False
        islayer4 = False
        for iRun, (runNr, hmap) in enumerate(inputHists_temp.iteritems()):      # loop over runs
            print runNr
            for hname, h in hmap.iteritems():       # loop over individual histograms
                isbpix = hname.find("Layer")!=-1
                islayer4 = hname.find("Layer4")!=-1
                
                # this part defines the lower and upper limits of the histograms
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
                    if hname not in hists[item]:
                        hists[item][hname] = hdefault.Clone()
                        hists_e[item][hname] = hdefault_e.Clone()
                        hists_sig[item][hname] = hdefault_sig.Clone()
                    if h.GetBinContent(1)==0:
                       failed = True 
                       continue  #alignment did not finish successfull
                    for bin in range(1,h.GetNbinsX()+1):
                        c = h.GetBinContent(bin)
                        if c==0: continue
                        e = h.GetBinError(bin)
                        hists[item][hname].Fill(c)
                        hists_e[item][hname].Fill(e)
                        hists_sig[item][hname].Fill(c/e if e>0 else 0)
                else:   # results in bpix are separated in outer and inner ladders
                    if hname+"_out" not in hists[item]:
                        hists[item][hname+"_out"] = hdefault.Clone()
                        hists_e[item][hname+"_out"] = hdefault_e.Clone()
                        hists_sig[item][hname+"_out"] = hdefault_sig.Clone()
                    if hname+"_in" not in hists[item]:
                        hists[item][hname+"_in"] = hdefault.Clone()
                        hists_e[item][hname+"_in"] = hdefault_e.Clone()
                        hists_sig[item][hname+"_in"] = hdefault_sig.Clone()
                    for bin in range(1,h.GetNbinsX()+1):
                        c = h.GetBinContent(bin)
                        if c==0: continue
                        e = h.GetBinError(bin)
                        i = 0
                        if islayer4: i=1    # numbering of inner and outer ladders in layer4 is inverted
                        if bin%2==i:
                            hists[item][hname+"_out"].Fill(c)
                            hists_e[item][hname+"_out"].Fill(e)
                            hists_sig[item][hname+"_out"].Fill(c/e if e>0 else 0)     # avoid dividing by zero
                        else:
                            hists[item][hname+"_in"].Fill(c)
                            hists_e[item][hname+"_in"].Fill(e)
                            hists_sig[item][hname+"_in"].Fill(c/e if e>0 else 0)     # avoid dividing by zero
    return changeAxisDict(hists),changeAxisDict(hists_e),changeAxisDict(hists_sig)      # change axis such that first key defines structure and variable and second key defines hit number

# method to draw the combined histograms
def drawCombinedHists(hmaps,plotDir):
    for ih,hmap in enumerate(hmaps):    # ih loops over movement, error and significance hists
        objectDict = {}
        for structure in objects:
            objectDict[structure[0]] = structure[1]
        
        paramDict = {}
        parameters_temp = parameters
        if ih==1 : parameters_temp=parameters_e     # get correct parameters
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
        leg = ROOT.TLegend(.56, .76, .88, .88)
        leg.SetNColumns(2)
        leg.SetBorderSize(1)
        leg.SetLineWidth(0)
        gStyle.SetFrameLineWidth(2)
        c = ROOT.TCanvas(randomName(),"",700,600)
        hists = {}
        isbpix = False
        for ig,(name,histCollection) in enumerate(hmap.iteritems()):      # ig loops over the combination of different detector parts and variables
            hists[ig] = {}
            isbpix = name.find("Layer")!=-1
            structure = name.split("_")[2]      # get structure from name (e.g. Layer1)
            param = name.split("_")[0]      # get histogram type from name (e.g. movement)
            for io,histOption in enumerate(["50Hits","100Hits","300Hits","500Hits"]):       # loop over different hit options
                hist = mergeOverflow(histCollection[histOption],True)
                hist.SetStats(0)
                hist.SetTitle(";{};{}".format(paramDict[param].label,"Entries"))
                gPad.SetLeftMargin(100)
                hist.SetMarkerColor(objectDict[structure])
                #  ~hist.SetLineColor(io+1 if io<=1 else io+2)
                hist.SetLineColor(io+6)
                hist.SetLineWidth(2)
                hist.SetMaximum(1.3*hist.GetMaximum())
                hist.Draw("hist" if io==0 else "hist same")     # draw all hit option in the same plot
                hist.GetYaxis().SetTitleOffset(0.95)
                hists[ig][histOption] = hist.Clone()
                #  ~leg.AddEntry(hist, histOption, "l")
                leg.AddEntry(hist, histOption+"({})".format(int(hist.GetEntries())), "l")
            gStyle.SetHistTopMargin(0.)
            hist_temp=hists[ig].itervalues().next()
            if ih==0 or ih==2:  # show different thresholds/veto lines depending on the histogram type
                line.DrawLine(-paramDict[param].cut, 0, -paramDict[param].cut,hist_temp.GetMaximum())
                line.DrawLine(+paramDict[param].cut, 0, +paramDict[param].cut,hist_temp.GetMaximum())
            if ih==0 or ih==1:
                if ih==0: line_e.DrawLine(-paramDict[param].veto, 0, -paramDict[param].veto,hist_temp.GetMaximum())
                line_e.DrawLine(+paramDict[param].veto, 0, +paramDict[param].veto,hist_temp.GetMaximum())
            gPad.RedrawAxis()
            text = ROOT.TLatex()
            text.SetTextSize(0.04)
            text.DrawLatexNDC(.1, .91, "#scale[1.2]{#font[61]{CMS}} #font[52]{Private Work}")
            text.DrawLatexNDC(.6, .91, "2018 pp collisions")
            text.DrawLatexNDC(.59, .645, structure+name.split("_")[3] if isbpix else structure)
            leg.Draw();
            if ih==0 : save(name, plotDir+"/movements", endings=[".pdf",".root"])
            elif ih==1 : save(name, plotDir+"/errors", endings=[".pdf",".root"])
            else : save(name, plotDir+"/significance", endings=[".pdf",".root"])
            c.Clear()
            leg.Clear()

if __name__ == "__main__":
    #########Define the output directory#############
    plotDir = "./plots/PR_starting_2018B_diffHits"

    #########Define path of histograms###############
    searchPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/2018B_PRstartingGeometry_iterativ_diffHits/{}/HG_run*/DQM*.root"
    #  ~searchPath="/eos/cms/store/caf/user/dmeuser/PCL/condor_PCL_2018/2018B_PRstartingGeometry_iterativ_diffHits/{}/HG_run31708*/DQM*.root"
    
    # get input histograms from one DQM file per run
    inputHists = getInputHists(searchPath)
    
    # prepare combined histograms from multiple runs
    combinedHists = getCombinedHist(inputHists)
    
    # draw combined histograms
    drawCombinedHists(combinedHists,plotDir)

