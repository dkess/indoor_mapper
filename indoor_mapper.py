from copy import deepcopy
from datetime import datetime
from enum import IntEnum
import itertools
import json
import sys

DIRECTIONS = 'wdsa'

class Direction(IntEnum):
    forward = 0
    right = 1
    backward = 2
    left = 3

    def opposite(self):
        return self + Direction.backward

    def __add__(self, other: 'Direction') -> 'Direction':
        return Direction((self.value + other.value) % 4)

    def __sub__(self, other: 'Direction') -> 'Direction':
        return Direction((self.value - other.value) % 4)

    def letter(self):
        return DIRECTIONS[self.value]


class MyDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if 'afterturn' in obj:
            obj['afterturn'] = Direction[obj['afterturn']]
        elif 'branches' in obj:
            obj['branches'] = {Direction[d]: v for d, v in obj['branches'].items()}
        return obj

def dump_dbfile(db, f):
    db = deepcopy(db)
    for node in db['nodes']:
        node['branches'] = {d.name: v for d, v in node['branches'].items()}
    for entry in db['log']:
        entry['afterturn'] = entry['afterturn'].name
    json.dump(db, f)

def letter_dir(letter: str) -> Direction:
    return Direction(DIRECTIONS.index(letter))

def main():
    db_fname = 'nodes'
    time = datetime.now().isoformat()
    command = sys.argv[1]
    if command == 'begin':
        # create a new db
        db = {'nodes': [{'branches': {Direction.forward: None},
                         'description': 'root node'}],
              'log': [{'afterturn': Direction.forward,
                       'time_enter': time,
                       'node': 0}]}
        with open(db_fname, 'w') as f:
            dump_dbfile(db, f)
    elif command == 'fork':
        try:
            dirs = sys.argv[2]
        except IndexError:
            dirs = ''

        try:
            force_turn = letter_dir(sys.argv[3])
        except IndexError:
            force_turn = ''

        with open(db_fname) as f:
            db = json.load(f, cls=MyDecoder)
        currently_facing = db['log'][-1]['afterturn']
        behind = currently_facing.opposite()
        branches = set(letter_dir(d) for d in dirs)
        abs_branches = set(x + currently_facing for x in branches)
        abs_branches.add(behind)
        last_node_id = db['log'][-1]['node']
        
        # check if we are definitely at an already existing node
        node_id, node = next(((n, node) for n, node in enumerate(db['nodes'])
                              if node['branches'].get(behind) == last_node_id),
                             (-1, None))

        if node:
            # do an extra check that this node is consistent
            if node['branches'].keys() != abs_branches:
                print('Something is wrong!')
                print('It looks like you\'re at node', node_id)
                print('({})'.format(node['description']))
                print('But you gave directions:   {}'.format(
                    ' '.join(x.name for x in branches)))
                print('That conflict with stored: {}'.format(
                    ' '.join((x - currently_facing).name for x in
                             node['branches'].keys())))
                print('Exiting without saving changes.')
                return
            else:
                print('You are at node {} ({})'.format(
                    node_id, node['description']))
                db['nodes'][last_node_id][currently_facing] = node_id
        elif len(branches) <= 1:
            # create a new node
            node_id = len(db['nodes'])
            node = {'branches': {d: None for d in abs_branches},
                    'description': ''}
            node['branches'][behind] = last_node_id
            db['nodes'].append(node)
        else:
            # Generate the list of possible existing nodes we could be on
            possible = [(n, node) for n, node in enumerate(db['nodes'])
                        if (node['branches'].keys() == abs_branches and
                                node['branches'][behind] == None)]

            print('Pick the node you are on, or type a new description:')
            for choice_id, choice in possible:
                print('{}: {}'.format(choice_id, choice['description']))
            choice = input('-> ')
            try:
                node_id = int(choice)
                node = db['nodes'][node_id]
            except ValueError:
                # create a new node
                node_id = len(db['nodes'])
                node = {'branches': {d: None for d in abs_branches},
                        'description': choice}
                node['branches'][behind] = last_node_id
                db['nodes'].append(node)

        db['nodes'][last_node_id]['branches'][currently_facing] = node_id
        # Now the node and id are saved in the node and node_id vars
        # We now need to decide which direction the user should be directed in
        # We accomplish this by doing BFS until an unexplored node is found
        distance = {}
        parent = {}

        frontier = []
        distance[node_id] = 0
        parent[node_id] = None

        frontier.append(node_id)
        found_unexplored = False
        while frontier:
            current = frontier.pop(0)
            current_node = db['nodes'][current]
            for d in sorted(current_node['branches'].keys(),
                            key=lambda x: x - currently_facing + Direction.right,
                            reverse=True):
                next_id = current_node['branches'][d]
                if next_id == None or next_id not in distance:
                    distance[next_id] = distance[current] + 1
                    parent[next_id] = current, d
                    if next_id == None:
                        found_unexplored = True
                        if current == node_id and d - currently_facing == force_turn:
                            break
                    frontier.append(next_id)
            if found_unexplored:
                break

        if not found_unexplored:
            print('You are done exploring! To get back to root:')
            directions = []
            current = 0
            while parent[current]:
                directions.append(parent[current])
                current, _ = parent[current]
            for nid, d in reversed(directions):
                t = d
                d = d - currently_facing
                currently_facing = t
                print(nid, d.name, db['nodes'][nid]['description'])
            db['log'].append({'afterturn': Direction.forward,
                              'time_enter': time,
                              'node': node_id})
        else:
            current = None
            while current != node_id:
                current, d = parent[current]
            print('You should turn', (d - currently_facing).name)

            db['log'].append({'afterturn': d,
                              'time_enter': time,
                              'node': node_id})

        print('Saving database...')
        with open(db_fname, 'w') as f:
            dump_dbfile(db, f)
        print('Done!')

    elif command == 'undo':
        with open(db_fname) as f:
            db = json.load(f, cls=MyDecoder)

        last_node_id = db['log'][-1]['node']
        last_node = db['nodes'][db['log'][-1]['node']]
        if last_node_id == len(db['nodes']) - 1:
            print('Deleting last node')
            db['nodes'] = db['nodes'][:-1]
        db['log'] = db['log'][:-1]
        print('Saving database...')
        with open(db_fname, 'w') as f:
            dump_dbfile(db, f)
        print('Done!')

if __name__ == '__main__':
    main()
