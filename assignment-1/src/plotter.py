import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pyomo.environ as po
import time
from datetime import datetime
import itertools
import sys
from optparse import OptionParser
import data

################ PLOTTING ################

class Timeslot():
    def __init__(self, start, end, color, title):
        self.start = start
        self.end = end
        self.color = color
        self.title = title

def applyTimeslots(offset, limit, timeslots, ax):
    for timeslot in timeslots:
        ax.fill_between([offset + 0.05, limit - 0.05], [timeslot.start + 0.05, timeslot.start + 0.05], [timeslot.end - 0.05,timeslot.end - 0.05], color=timeslot.color, edgecolor='k', linewidth=0.5, alpha=0.4
                        )
        ax.text(float(limit - offset) / 2 + offset, (timeslot.start + timeslot.end) / 2, timeslot.title, ha="center", va="center", fontsize=12)
        
def plotDay(timeslots):
    width = 10
    height = 8
    
    fig = plt.figure(figsize=(width, height))
    
    margin = 0.3
    
    ax = fig.add_subplot(111)
    ax.yaxis.grid()
    ax.set_ylabel("Time")
    ax.axes.get_xaxis().set_visible(False)
    fig.gca().invert_yaxis()

    applyTimeslots(margin, width - margin, timeslots, ax)
    
    ax.set_title("Day")
    
    plt.show()
    
def plotWeek(timeslotDays, dayStartAndEnd = None, title = None):
    width = 15
    height = 8
    weekdays = 7
    
    fig = plt.figure(figsize=(width, height))
    
    margin = 0.3
    
    ax = fig.add_subplot(111)
    ax.yaxis.grid()
    
    if dayStartAndEnd != None:
        (start, end) = dayStartAndEnd
        
        plt.yticks(range(start, end + 1))
        fig.gca().set_ylim([start,end])
    
    ax.set_ylabel("Time")
    #ax.axes.get_xaxis().set_visible(False)
    
    fig.gca().invert_yaxis()
    
    dayWidth = width / weekdays
    
    def genDays(): 
        days = ["Monday", "Tuesday", "Wensday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        
        fig.gca().set_xlim([0,len(days)])
        

        for i, day in enumerate(days):
            yield (day, i * dayWidth + (dayWidth / 2))
            
    tickedDays = list(genDays())
    
    plt.xticks(list(map(lambda x: x[1], tickedDays)), list(map(lambda x: x[0], tickedDays)))
    
    for i, dayTimeslots in enumerate(timeslotDays):
        offset = i * dayWidth
        
        applyTimeslots(offset, offset + dayWidth, dayTimeslots, ax)

    if title != None:
        ax.set_title(title)
    else:
        ax.set_title("Week")
    
    plt.show()
    
def plotFor(events, modelDataMapping, model, week, rooms, withBadSlots = False):
    timeslots = [ [] for i in range(7) ]

    color_map = {}

    colorsAsList = list(mcolors.TABLEAU_COLORS.items())

    for i, k in enumerate(events):
        color_map[k] = colorsAsList[i]
        
    dayStart = 8

    # plot data
    for e in modelDataMapping.E:
        for r in rooms:
            for (h, d, w) in modelDataMapping.P:
                if w != week:
                    continue
                    
                s = set(modelDataMapping.B[r])
                
                namedEvent = modelDataMapping.namedEvents[e]

                value = po.value(model.x[e,r,h,d,w])

                if value != 0:
                    color = color_map[namedEvent[0]]

                    teachersThatCanTeachThis = [str(teacherIdx) for teacherIdx in modelDataMapping.courseIdToTeacherMapping[e]]

                    timeslots[d].append(Timeslot(h + dayStart, h + dayStart + namedEvent[1]["duration"], color, namedEvent[1]["id"] + "\n" + ", ".join(teachersThatCanTeachThis) + "\n" + str(r)))
                    
                if withBadSlots:
                    if (h, d, w) in s:
                        timeslots[d].append(Timeslot(h + dayStart, h + dayStart + 1, "red", ""))
                        continue

    roomStr = ", room ".join(list(map(lambda x: str(x), rooms)))
                    
    plotWeek(timeslots, (7, 22), "Week " + str(week) + ", room " + roomStr)

def plotFile():
    dataImporter = data.Data("data/small")
    import model
    slots = dataImporter.slots
    banned = dataImporter.banned
    events = dataImporter.events
    teachers = dataImporter.teachers
    students = dataImporter.students
    rooms = dataImporter.rooms

    m = po.ConcreteModel("timetable")
    import cloudpickle

    with open('ttmilp_model.pkl', mode='rb') as file:
        m = cloudpickle.load(file)

    modelDataMapping = model.prepareModel(events, students, teachers, slots, banned, rooms)

    plotFor(events, modelDataMapping, m, week=17, rooms=[0,1,2,3,4,5])


if __name__ == "__main__":
    plotFile()
