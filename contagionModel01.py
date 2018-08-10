import networkx as nx
import random
from enum import Enum

from mesa import Agent, Model
from mesa.time import RandomActivation, BaseScheduler
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector

class RandomSingleActivation(BaseScheduler):
    def step(self):
        """ Executes the step of a single randomly chosen agent.
        """
        random.choice(self._agents).step()
        self.steps += 1
        self.time += 1

class State(Enum):
    HEALTHY = 0
    INFECTED = 1

class Event(Enum):
    INFECT = 0
    RECOVER = 1
    NOTHING = 2

class DiseaseAgent(Agent):
    def __init__(self,unique_id,model):
        super().__init__(unique_id,model)
        self.state = State.HEALTHY
        self.event = Event.NOTHING
        self.cause = -100

    def step(self):
        rand_inf = random.random()
        rand_rec = random.random()
        neighbour_nodes = self.model.grid.get_neighbors(self.pos,include_center=False)
        neighbour_agents = self.model.grid.get_cell_list_contents(neighbour_nodes)
        neighbour = random.choice(neighbour_agents)
        # infect a neighbour?
        #print("Tick %d: Checking agent %d" % (self.model.schedule.steps,self.unique_id))
        if self.state == State.INFECTED and rand_inf < self.model.percInfect:
            if not neighbour.state == State.INFECTED:
                neighbour.infect(self.unique_id)
        # recover?
        if self.state == State.INFECTED and rand_rec < self.model.percRecover:
            self.recover()

    def infect(self,sender_id=-1):
        print("Tick %d: agent %d was infected by agent %d" % (self.model.schedule.steps,self.unique_id,sender_id))
        self.event = Event.INFECT
        self.cause = sender_id
        self.state = State.INFECTED

    def recover(self):
        print("Tick %d: agent %d recovers" % (self.model.schedule.steps,self.unique_id))
        self.event = Event.RECOVER
        self.state = State.HEALTHY
        self.cause = -100

class DiseaseModel(Model):
    def __init__(self,N,initInfected,percInfect,percRecover,intervention):
        self.running = True
        self.num_agents = N
        self.initInfected = initInfected
        self.percInfect = percInfect
        self.percRecover = percRecover
        self.intervention = intervention

        #self.grid = nx.ErdosRenyiGraph(self.num_agents,)
        self.G = nx.complete_graph(self.num_agents)
        self.grid = NetworkGrid(self.G)
        self.schedule = RandomSingleActivation(self)

        # create and initialise agents
        for i,node in enumerate(self.G.nodes):
            a = DiseaseAgent(i,self)
            self.schedule.add(a)
            self.grid.place_agent(a,node)
        # make some agents initially infected
        for a in filter(lambda a: a.unique_id in initInfected, self.schedule.agents): #random.sample(self.schedule.agents, self.initInfected):
            a.infect()

        # set up data collection
        self.datacollector = DataCollector(agent_reporters = {"State":"state","Event":"event","Cause":"cause"})

    def reset_events(self):
        for a in self.schedule.agents:
            a.event = Event.NOTHING
            a.cause = -100

    def step(self):
        self.reset_events()
        # update model
        self.schedule.step()
        # perform intervention if necessary
        if self.intervention is not None:
            self.intervention.apply(self)
        # perform data collection
        self.datacollector.collect(self)

def get_agent_by_id(agents,idx):
    return [a for a in agents if a.unique_id == idx][0]

# simple intervention functor
class Intervention:
    def __init__(self,trace):
        self.trace = trace

    def apply(self,model):
        tick = model.schedule.steps-1
        agents = model.schedule.agents
        for idx in [ a.unique_id for a in agents ]:
            a = get_agent_by_id(agents,idx)
            if a.event == Event.INFECT and self.trace['Event'][(tick,idx)] != Event.INFECT:
                print("Tick %d: preventing agent %d from becoming infected" % (tick,idx))
                a.recover()

def run(numAgents, initInfected, percInfect, percRecover, numTicks, name, intervention=None):
    random.seed(1)
    print("+++ INIT %s +++" % name)
    model = DiseaseModel(numAgents,initInfected,percInfect,percRecover,intervention)
    print("+++ START %s +++" % name)
    for i in range(0,numTicks):
        model.step()
    #model.datacollector.collect(model)

    # model analysis
    res = model.datacollector.get_agent_vars_dataframe()
    res.to_csv("./%s.csv" % name)
    return res

def main():
    # model parameters
    numAgents = 10
    initInfected = [0,1]
    percInfect = 0.5
    percRecover = 0.05
    numTicks = 10

    # scale up ticks artifically
    numTicks = numTicks*numAgents

    # base run
    orig_trace = run(numAgents, initInfected, percInfect, percRecover, numTicks, "tr_base")
    orig_trace.to_dict()
    orig_infected_in_final = [ idx for (step,idx) in orig_trace['State'].keys() if step == numTicks-1 and orig_trace['State'][(step,idx)] == State.INFECTED ]
    print(orig_infected_in_final)

    causal_rel = {}

    # simple counterfactual experiment 1
    for a in initInfected:
        name = "tr_simpleCF1_wo%d" % a
        trace = run(numAgents, [b for b in initInfected if a != b], percInfect, percRecover, numTicks, name)
        trace_infected_in_final = [ idx for (step,idx) in trace['State'].keys() if step == numTicks-1 and trace['State'][(step,idx)] == State.INFECTED ]
        print(trace_infected_in_final)
        causal_rel[name] = list(set(orig_infected_in_final)-set(trace_infected_in_final))
    # simple counterfactual experiment 2
    for a in initInfected:
        name = "tr_simpleCF2_wo%d" % a
        run(numAgents, [b for b in initInfected if a != b], percInfect, percRecover, numTicks, name)
        trace_infected_in_final = [ idx for (step,idx) in trace['State'].keys() if step == numTicks-1 and trace['State'][(step,idx)] == State.INFECTED ]
        print(trace_infected_in_final)
        causal_rel[name] = list(set(orig_infected_in_final)-set(trace_infected_in_final))

    # intervention-based counterfactual experiment
    for a in initInfected:
        name = "tr_intervCF_wo%d" % a
        intervention = Intervention(orig_trace)
        trace = run(numAgents, [b for b in initInfected if a != b], percInfect, percRecover, numTicks, name, intervention)
        trace_infected_in_final = [ idx for (step,idx) in trace['State'].keys() if step == numTicks-1 and trace['State'][(step,idx)] == State.INFECTED ]
        print(trace_infected_in_final)
        causal_rel[name] = list(set(orig_infected_in_final)-set(trace_infected_in_final))

    print(causal_rel)

if __name__ == "__main__":
    main()
