## DEAP tree visualiser
This is a program designed to make visualisation of the trees produced by deap easy! (hopefully)

This module consists of two parts:
## Tree
A class that takes a deap expression and breaks it down into a tree based structure that can be more easily reasoned with. In general this is just an intermediate step to graphically visualising a tree. But can be a useful tool for visualising in an interactive session like a debugger.
```python
tree = Tree.of(gp_individual_to_visualise, pset)
```
## TreeDrawer
A class that takes a given tree, and draws it for some input. eg.
```python
TreeDrawer().save_graph("base_tree_drawer_example.png", tree, 7)
```
Is designed to be extensible if you want it as shown in the [Examples](##examples).

## Examples
```python
tree = Tree.of(best_individual, pset)
# Visualise for some specific input
TreeDrawer().save_graph("base_tree_drawer_example.png", tree, 7)
```
![drawing symbolic regression without any changes, for the input 7](./examples/base_tree_drawer_example.png)
