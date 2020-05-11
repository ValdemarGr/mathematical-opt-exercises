import pyomo.environ as po
import data as imp

dataImporter = imp.Data("../data/medium")

slots = dataImporter.slots#[:50]
banned = dataImporter.banned
events = dataImporter.events
teachers = dataImporter.teachers
students = dataImporter.students
rooms = ["one", "two"]


class ModelDataMapping:
    def __init__(self, E, P, R, namedEvents, model, result):
        self.E = E
        self.P = P
        self.R = R
        self.namedEvents = namedEvents
        self.model = model
        self.result = result


def prepareModel(events, students, teachers, slots, banned, rooms):
    R = list(range(len(rooms)))
    namedEvents = [(eventSet, e) for eventSet in events for e in events[eventSet]]
    E = list(range(len(namedEvents)))
    P = [(s["hour"], s["day"], s["week"]) for s in slots]
    preparedBanned = [(b["hour"], b["day"], b["week"]) for b in banned]

    # Events are a dict of name -> list[dict]
    # where dict is a know struct (an event)

    domain = [(e, r, p[0], p[1], p[2]) for e in E for r in R for p in P]

    m = po.ConcreteModel("timetable")

    m.x = po.Var(domain, bounds=(0, 1), within=po.Binary)

    m.value = po.Objective(expr=sum(m.x[(e, r, p)] for e in E for r in R for p in P), sense=po.minimize)

    m.scheduled = po.ConstraintList()

    for e in E:
        m.scheduled.add(expr=sum(m.x[(e, r, p)] for p in P for r in R) == 1)

    m.collision = po.ConstraintList()

    m.overlap = po.ConstraintList()

    def duration(eventIndex):
        return namedEvents[eventIndex][1]["duration"]

    for r in R:
        for p in P:
            (h, d, w) = p

            m.collision.add(sum(m.x[(e, r, p)] for e in E) <= 1)

            if h != 0:
                m.overlap.add(
                    sum(sum(m.x[(e, r, (i, d, w))] for i in range(max(0, h - duration(e) + 1), h)) for e in E) <= 1)

    res = po.SolverFactory("glpk").solve(m, tee=(False))

    o = ModelDataMapping(E, P, R, namedEvents, m, res)

    return o

modelDataMapping = prepareModel(events, students, teachers, slots, banned, rooms)

es = [1,20,21,22]

print(modelDataMapping.result.Solver.status)

for e in es:
    for r in modelDataMapping.R:
        for p in modelDataMapping.P:
            value = po.value(modelDataMapping.model.x[e,r,p])

            if value != 0:
                print(value)
                print(e,r,p)