#! /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from optparse import OptionParser
import data
import model

from datetime import datetime
import cloudpickle

def main():
    usage = "usage: %prog [options] DIRNAME"
    parser = OptionParser(usage)
    parser.add_option("-e", "--example", type="string", dest="example",
                      default="value", metavar="[value1|value2]", help="Explanation [default: %default]")
    (options, args) = parser.parse_args()  # by default it uses sys.argv[1:]
    if not len(args) == 1:
        parser.error("Directory missing")

    dirname = args[0]
    
    import pyomo.environ as po
    import time
    from datetime import datetime
    import itertools

    dataImporter = data.Data(dirname)

    slots = dataImporter.slots
    banned = dataImporter.banned
    events = dataImporter.events
    teachers = dataImporter.teachers
    students = dataImporter.students
    rooms = dataImporter.rooms
    
    modelDataMapping = model.prepareModel(events, students, teachers, slots, banned, rooms)

    m, result = model.solveModel(modelDataMapping, debug=True)
    
    #m.write("ttmilp.lp")

    #with open('ttmilp_model.pkl', mode='wb') as file:
    #    cloudpickle.dump(m, file)
#
    #
    #with open('ttmilp_res.pkl', mode='wb') as file:
    #    cloudpickle.dump(result, file)


if __name__ == "__main__":
    main()
