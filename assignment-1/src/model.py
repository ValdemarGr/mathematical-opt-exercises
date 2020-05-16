################ MODEL ################
import pyomo.environ as po
import time
from datetime import datetime
import itertools

def uniq(lst):
    last = object()
    for item in lst:
        if item == last:
            continue
        yield item
        last = item

class ModelDataMapping:
    def __init__(self, E, E_w, E_c_w, P, R, D, D_w, T, B, S, Q, Q_w, Q_c_w, O, C, namedEvents, indexedRooms, teacherPairs, courseIdToTeacherMapping, eventLookup, eventIdToCourseId, dayWeekMaxHrPairs):
        self.E = E
        self.E_w = E_w
        self.E_c_w = E_c_w
        self.P = P
        self.R = R
        self.D = D
        self.D_w = D_w
        self.T = T
        self.B = B
        self.S = S
        self.Q = Q
        self.Q_w = Q_w
        self.Q_c_w = Q_c_w
        self.O = O
        self.C = C
        self.namedEvents = namedEvents
        self.indexedRooms = indexedRooms
        self.teacherPairs = teacherPairs
        self.courseIdToTeacherMapping = courseIdToTeacherMapping
        self.eventLookup = eventLookup
        self.eventIdToCourseId = eventIdToCourseId
        self.dayWeekMaxHrPairs = dayWeekMaxHrPairs

def prepareModel(events, students, teachers, slots, banned, rooms):
    rooms_as_list = list(rooms.items())
    
    R = list(range(len(rooms_as_list)))
    namedEvents = [(eventSet, e) for eventSet in events for e in events[eventSet]]
    E = list(range(len(namedEvents)))
    P = [(s["hour"], s["day"], s["week"]) for s in slots]
    preparedBanned = [(b["hour"], b["day"], b["week"]) for b in banned]
    
    eventIdToIndex = dict([(e[1]["id"], i) for i, e in enumerate(namedEvents)])
    teacherPairs = list(teachers.items())
    T = range(len(teacherPairs))

    def indexedTeacherEvents():
        for teacherId, eventsForTeacher in teacherPairs:
            onlyEvents = [e["events"] for e in eventsForTeacher]

            flattenedEvents = [eventIdToIndex[b] for a in onlyEvents for b in a]

            yield flattenedEvents
    
    D = list(indexedTeacherEvents())
    
    studentPairs = list(students.items())
    S = range(len(studentPairs))
    
    def indexedStudentEvents():
        for studentId, eventsForStudent in studentPairs:
            onlyEvents = [e["events"] for e in eventsForStudent]

            flattenedEvents = [eventIdToIndex[b] for a in onlyEvents for b in a]

            yield flattenedEvents
            
    U = list(indexedStudentEvents())
    
    def busyRoomsForTimeAndBanned():
        # For O(1) lookup
        PAsSet = set(P)
        
        def formatEvent(e):
            return (e["hour"], e["day"], e["week"])

        for roomIndex, r in enumerate(rooms_as_list):
            (k, v) = r

            formattedBusyEvents = list(map(lambda e: formatEvent(e), v["busy"]))
            
            # filter out all events that do not exist in the timeslots data-set
            def removeInvalidTimes():
                for p in formattedBusyEvents:
                    if p in PAsSet:
                        yield p
                        
            def removeInvalidBannedTimes():
                for p in preparedBanned:
                    if p in PAsSet:
                        yield p
            
            yield (roomIndex, list(removeInvalidTimes()) + list(removeInvalidBannedTimes()))

    B = dict(busyRoomsForTimeAndBanned())
    
    # courseId to teacher mapping
    courseIdToTeacherMapping = [ [] for i in range(len(E)) ]

    for teacherIdx, d in enumerate(D):
        for e in d:
            courseIdToTeacherMapping[e].append(teacherIdx)
            
    def eventLookup():
        for i, (k, v) in enumerate(namedEvents):
            yield (v["id"], i)
            
    def eventIdToCourseId():
        for courseId, event in namedEvents:
            yield (event["id"], courseId)
            
    def dayWeekMaxHrPairs():
        def genDWHPairs():
            for (h,d,w) in P:
                yield ((d,w), h)
        
        dwh = list(genDWHPairs())
        
        for k in dict(dwh):
            yield (k, max(map(lambda x: x[1], filter(lambda x: x[0] == k, dwh))))
            
    EidtoCid = dict(list(eventIdToCourseId()))
    
    elook = dict(list(eventLookup()))
    
    dwmhrp = dict(dayWeekMaxHrPairs())
            
    def orderStudentClassesIntoCourses():
        for u in U:
            # Get course type
            courseIdMap = {}
            
            for e in u:
                courseId = namedEvents[e][0]
                courseIdMap.setdefault(courseId,[]).append(e)
                
            yield courseIdMap
            
    Q = list(orderStudentClassesIntoCourses())
    
    def genO():
        for ((d,w), maxHr) in dwmhrp.items():
            # lectures in hr 8 for all is rating 5 bad
            # lectuers in hr 16 for mon, tues, wed, thur is rating 3 bad
            # lectures in hr 17 for -||- is rating 4 bad
            # lectures in hr 15, 16 and 17 for fri is rating 6 bad
            def fillNs(start, end, n = 1):
                return list(map(lambda h: ((h,d,w), n), range(start, end + 1)))
            
            offset = 8
            
            if d in list(range(0, 4)):
                out = [((8 - offset,d,w), 5)] + fillNs(9 - offset,15 - offset) + [((16 - offset,d,w), 3), ((17 - offset,d,w), 4)] + fillNs(18 - offset,maxHr, 10)
            else:
                out = [((8 - offset,d,w), 5)] + fillNs(9 - offset,14 - offset) + [((15 - offset,d,w), 6), ((16 - offset,d,w), 6), ((17 - offset,d,w), 6)]  + fillNs(18 - offset,maxHr, 10)
                
            for o in out:
                yield o
                
    O = dict(list(genO()))
    
    C_build = {}

    for e in E:
        courseId = namedEvents[e][0]
        C_build.setdefault(courseId,[]).append(e)
            
    C = list(map(lambda x: x[1], list(C_build.items())))
    
    E_w = {}
    
    for _, e in namedEvents:
        eventIndex = eventIdToIndex[e["id"]]
        E_w.setdefault(e["week"], []).append(eventIndex)
        
    # Q = list[StudentIdx -> dict[CourseId -> list[EventIdx]]]
    # Q_w = dict[Week -> dict[StudentIdx -> list[EventIdx]]]
    allWeeks = list(set([w for (h,d,w) in P]))
    
    def genQ_w():
        weekMap = dict([(w, {}) for w in allWeeks])
        for studentIdx, q in enumerate(Q):
            for courseId, es in q.items():
                for e in es:
                    weekMap[namedEvents[e][1]["week"]].setdefault(studentIdx, []).append(e)

        return weekMap
        
    Q_w = genQ_w()
    
    # Q_w = dict[CourseId -> dict[Week -> dict[StudentIdx -> list[EventIdx]]]]
    
    def genQ_c_w():
        courseMap = dict([(idx, dict([(w, {}) for w in allWeeks])) for idx, c in enumerate(C)])
        
        for idx, c in enumerate(C):
            cs = set(c)
            for studentIdx, q in enumerate(Q):
                for courseId, es in q.items():
                    for e in es:
                        if e in cs:
                            courseMap[idx][namedEvents[e][1]["week"]].setdefault(studentIdx, []).append(e)
                            
        return courseMap

    Q_c_w = genQ_c_w()
    
    E_c_w = {}
    
    for courseIdx, c in enumerate(C):
        for w in allWeeks:
            E_c_w.setdefault(courseIdx, {})[w] = []
        
        for e in c:
            weekForEvent = namedEvents[e][1]["week"]
            E_c_w[courseIdx][weekForEvent].append(e)
    
    # D = list[TeacherIdx -> list[EventIdx]]
    # D_w = dict[Week -> dict[TeacherIdx -> list[EventIdx]]]
    D_w = {}
    
    for w in allWeeks:
        D_w[w] = {}
    
    for teacherIdx, d in enumerate(D):
        for e in d:
            weekForEvent = namedEvents[e][1]["week"]
            D_w[weekForEvent].setdefault(teacherIdx, []).append(e)
            
    return ModelDataMapping(E, E_w, E_c_w, P, R, D, D_w, T, B, S, Q, Q_w, Q_c_w, O, C, namedEvents, rooms_as_list, teacherPairs, courseIdToTeacherMapping, elook, EidtoCid, dwmhrp)
        
def solveModel(preparedData, debug=False):
    def printD(*kwargs):
        if debug:
            print(datetime.time(datetime.now()), end=' - ')
            for a in kwargs:
                print(a, end = ' ')
            print('')
    
    preSovle = time.time()
    
    m = _solveModel(preparedData, debug)
    
    printD("Solving...")
    
    now = time.time()
        
    res = po.SolverFactory("gurobi").solve(m, tee=(debug))
    
    later = time.time()
    difference = int(later - now)
    entireDifference = int(later - preSovle)
    
    printD("Solved in", difference, "seconds")
    printD("Done in", entireDifference, "seconds")
    
    return m, res

def _solveModel(preparedData, debug=False):
    def printD(*kwargs):
        if debug:
            print(datetime.time(datetime.now()), end=' - ')
            for a in kwargs:
                print(a, end = ' ')
            print('')
    
    E = preparedData.E
    P = preparedData.P
    R = preparedData.R
    D = preparedData.D
    T = preparedData.T
    B = preparedData.B
    S = preparedData.S
    Q = preparedData.Q
    O = preparedData.O
    C = preparedData.C
    Q_w = preparedData.Q_w
    Q_c_w = preparedData.Q_c_w
    E_w = preparedData.E_w
    E_c_w = preparedData.E_c_w
    D_w = preparedData.D_w
    
    def duration(eventIndex):
        return preparedData.namedEvents[eventIndex][1]["duration"]
    
    printD("Generating 5d/3d matrix of size", len(E) * len(R) * len(P))
    domain = [(e, r, p[0], p[1], p[2]) for e in E for r in R for p in P]
    
    m = po.ConcreteModel("timetable")
    
    printD("Adding variable x")
    m.x = po.Var(domain, bounds = (0, 1), within=po.Binary)
    
    printD("Adding soft constraints")
    
    printD("Adding delta + y + z")
    daySet = list(set([d for (h,d,w) in P]))
    hrWeekSet = list(set([(h, w) for (h,d,w) in P]))
    
    dcDomain = [(c,d) for c in range(len(C)) for d in daySet]
    
    m.delta = po.Var(dcDomain, within=po.NonNegativeReals)
    
    m.y = po.Var(dcDomain, bounds = (0, 1), within=po.Binary)
    
    m.z = po.Var(range(len(C)), within=po.NonNegativeReals)
    
    m.delta_constraint = po.ConstraintList()
    
    bigM = len(E)
    
    # Delta_c,d = ...
    for c in range(len(C)):
        for d in daySet:
            m.delta_constraint.add(m.delta[(c,d)] == sum(
                sum(
                    sum(
                        m.x[e,r,(h,d,w)]
                    for r in R)
                for e in E_c_w[c][w])
            for (h,w) in hrWeekSet))
            
    # y constraints
    for c in range(len(C)):
        m.delta_constraint.add(sum(m.y[(c,d)] for d in daySet) <= (len(daySet) - 1))
    
    # z constraints
    for c in range(len(C)):
        for d in daySet:
            m.delta_constraint.add(m.z[c] <= (m.delta[(c,d)] + bigM * m.y[(c,d)]))
    
    printD("Adding beta")
    m.beta = po.Var(within=po.NonNegativeReals)
    m.beta_constraint = po.ConstraintList()
    
    for (h,d,w) in P:
        for _, q in (Q_w[w]).items():
            m.beta_constraint.add(m.beta >= sum(
                sum(
                    sum(m.x[(e,r,(i, d, w))] for i in range(max(0, h - duration(e) + 1), h + 1))
                for r in R)
            for e in q))
    
    printD("Adding ml")
    m.ml = po.Var(within=po.NonNegativeReals)
    
    m.ml_constraint = po.ConstraintList()
    
    for ((d,w), maxHr) in preparedData.dayWeekMaxHrPairs.items():
        for _, de in (D_w[w]).items():
            rangeToMaxHr = range(0, maxHr + 1)
            
            mlExpr = sum(
                sum(
                    sum(
                        m.x[e,r,(hPrime,d,w)]
                    for r in R)
                for hPrime in rangeToMaxHr)
            for e in de)
            
            m.ml_constraint.add(mlExpr <= m.ml)
                
    
    printD("Adding alpha")
    m.alpha = po.Var(within=po.NonNegativeReals)
    m.alpha_constraint = po.ConstraintList()
    m.alpha_constraint.add(m.alpha == sum(
        sum(
            sum(
                sum(m.x[(e,r,(i, d, w))] for i in range(max(0, h - duration(e) + 1), h + 1)) * O[(h,d,w)]
            for r in R)
        for e in E_w[w])
    for (h,d,w) in P))
    
    objExpr = m.alpha + m.ml - sum(m.z[c] for c in range(len(C))) + m.beta
    
    m.value = po.Objective(expr=objExpr , sense=po.minimize)
    
    printD("Adding hard constriants")
    
    m.do_not_exceed = po.ConstraintList()
    
    printD("Adding do not exceed day constraint")
    for r in R:
        for ((d,w), maxHr) in preparedData.dayWeekMaxHrPairs.items():
            for e in E_w[w]:
                m.do_not_exceed.add(sum(m.x[(e,r,(i, d, w))] for i in range(max(0, maxHr - duration(e) + 1), maxHr + 1)) == 0)
    
    m.scheduled = po.ConstraintList()
    
    printD("Adding scheduled constraint")
    
    def weekFor(e):
        return preparedData.namedEvents[e][1]["week"]
    
    for e in E:
        weekForE = weekFor(e)
        relevantPs = list(filter(lambda p: p[2] == weekForE, P))
        irellevantPs = list(filter(lambda p: p[2] != weekForE, P))
        
        m.scheduled.add(expr = sum(m.x[(e,r,h,d,w)] for (h,d,w) in relevantPs for r in R) == 1)
        m.scheduled.add(expr = sum(m.x[(e,r,h,d,w)] for (h,d,w) in irellevantPs for r in R) == 0)
    
    m.one_event_per_student_day = po.ConstraintList()
    
    printD("Adding one event per course per day per student")
    for ((d,w), maxHr) in preparedData.dayWeekMaxHrPairs.items(): 
        for c, _ in enumerate(C):
            for q in list(uniq(Q_c_w[c][w].values())):
                rangeToMaxHr = range(0, maxHr + 1)

                m.one_event_per_student_day.add(sum(sum(sum(m.x[e,r,h,d,w] for h in rangeToMaxHr) for e in q) for r in R) <= 1)
    
    m.presedence = po.ConstraintList()
    
    def getActivationDay(e, relevantPs):
        return sum(sum(m.x[e,r,h,d,w] * d for (h, d, w) in relevantPs) for r in R)
    
    printD("Adding presedence graph")
    for e2 in E:
        in_arcs = preparedData.namedEvents[e2][1]["in_arcs"]
        weekForE = weekFor(e2)
        relevantPs = list(filter(lambda p: p[2] == weekForE, P))
        
        for arcSourceId in in_arcs:
            e1 = preparedData.eventLookup[arcSourceId]
            
            m.presedence.add(getActivationDay(e2, relevantPs) - getActivationDay(e1, relevantPs) >= 1)
    
    m.no_teach_busy = po.ConstraintList()
    
    printD("Adding no classes in busy period constraint")
    for r in R:
        for (h,d,w) in B[r]:
            for e in E_w[w]:
                m.no_teach_busy.add(sum(m.x[(e,r,(i, d, w))] for i in range(max(0, h - duration(e) + 1), h + 1)) == 0)
        
    
    m.only_teach_one_class = po.ConstraintList()
    
    printD("Adding teacher only teaches one class at a time constriants")
    for h,d,w in P:
        for de in D_w[w].values():

            m.only_teach_one_class.add(sum(sum(sum(m.x[(e,r,(i, d, w))] for i in range(max(0, h - duration(e) + 1), h + 1)) for r in R) for e in de) <= 1)
    
    m.overlap = po.ConstraintList()
    
    printD("Adding overlap constriants")
    for r in R:
        for (h,d,w) in P:
            m.overlap.add(sum(sum(m.x[(e,r,(i, d, w))] for i in range(max(0, h - duration(e) + 1), h + 1)) for e in E_w[w]) <= 1)
            
    return m
            
