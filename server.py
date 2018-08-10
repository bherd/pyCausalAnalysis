from mesa.visualization.modules import NetworkModule
from mesa.visualization.ModularVisualization import ModularServer
from contagionModel01 import DiseaseModel, State

def network_portrayal(G):
    # The model ensures there is always 1 agent per node

    def node_color(agent):
        return {
            State.INFECTED: '#FF0000',
            State.HEALTHY: '#008000'
        }.get(agent.state)

    def edge_color(agent1, agent2):
        return '#e8e8e8'

    def edge_width(agent1, agent2):
        return 2

    def get_agents(source, target):
        return G.node[source]['agent'][0], G.node[target]['agent'][0]

    portrayal = dict()
    portrayal['nodes'] = [{'size': 6,
                           'color': node_color(agents[0]),
                           'tooltip': "id: {}<br>state: {}".format(agents[0].unique_id, agents[0].state.name),
                           }
                          for (_, agents) in G.nodes.data('agent')]

    portrayal['edges'] = [{'source': source,
                           'target': target,
                           'color': edge_color(*get_agents(source, target)),
                           'width': edge_width(*get_agents(source, target)),
                           }
                          for (source, target) in G.edges]

    return portrayal

def main():
    network = NetworkModule(network_portrayal, 500, 500, library='d3')

    N = 10
    percInfect = 0.5
    percRecover = 0.25

    server = ModularServer(DiseaseModel,
                           [network],
                           "Disease Model",
                           { "N":N, "percInfect":percInfect, "percRecover":percRecover})

    server.port = 8521 # The default
    server.launch()

if __name__ == "__main__":
    main()
