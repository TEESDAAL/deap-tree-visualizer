from dataclasses import dataclass, field
from typing import Any, Callable, Self, Optional
from deap import gp
import pygraphviz as pgv, os, numpy as np, numpy.typing as npt
from matplotlib import pyplot as plt
import PIL.Image

type TreeNode = gp.Primitive | gp.Terminal
type image = npt.ArrayLike | PIL.Image.Image


@dataclass
class Box[T]:
    """
    A mutable holder of some value
    Attributes
    ----------
    value : T
        Some value of the generic type T
    """
    value: T

@dataclass
class Tree[T]:
    """
    A tree representation of a given deap GP model

    Attributes
    ----------
    function : gp.Primitive | gp.Terminal
        The "node" in the tree, is either a function to call with the children as arguments, or a terminal.
    children : list[Tree]
        The children of this node.
    pset : gp.PrimitiveSetTyped
        The pset that this exists in the context of.
    value : Optional[T]
        The value of this tree after a given input (starts as none, will get set when this node is evaluated on some input)
    """
    function: TreeNode
    children: list["Tree"]
    pset: gp.PrimitiveSetTyped
    value: Optional[T] = None

    @staticmethod
    def of(model: list[TreeNode], pset: gp.PrimitiveSetTyped) -> 'Tree':
        """
        Create a new tree from a given gp individual and the pset.

        Parameters
        ----------
        model : list[gp.Primitive | gp.Terminal]
            The gp model to display
        pset : gp.PrimitiveSetTyped
            The pset associated with the model
        """
        return Tree._construct_tree(model, pset, Box(0))

    @staticmethod
    def _construct_tree(model: list[TreeNode], pset: gp.PrimitiveSetTyped, index: Box[int]) -> "Tree":
        function = model[index.value]
        index.value += 1
        return Tree(function, [Tree._construct_tree(model, pset, index) for _ in range(function.arity)], pset)


    def __repr__(self) -> str:
        """
        Convert the tree into a string representation, should be the same as the original model

        Returns
        -------
        str
            The string representation of the tree (can be compiled by gp.compile)
        """
        return self.function.format(*self.children)

    def compile(self) -> Callable[..., T]:
        """
        Convert the tree into a runnable function

        Returns
        -------
        Callable[..., T]
            The function version of this tree.
        """
        return gp.compile(self, pset=self.pset)

    def id(self) -> str:
        """
        A unique identifier for this model (uses the memory address/id function).

        Returns
        -------
        str
            A unique identifier for this object.
        """

        return str(id(self))

    def _evaluate_all_nodes(self, *args) -> Any:
        self.value = self.compile()(*args)

        for child in self.children:
            child._evaluate_all_nodes(*args)

    def nodes(self) -> list["Tree"]:
        """
        Returns a flattened version of the tree

        Returns
        -------
        list[Tree]
            A list of nodes, which is all nodes in this tree, in recursive depth first order
        """
        return [self] + sum((child.nodes() for child in self.children), [])


@dataclass
class TreeDrawer:
    drawing_method: list[tuple[Callable[[Tree], bool], Callable[[pgv.AGraph, Tree], None]]] = field(default_factory=list)

    def __post_init__(self):
        self.drawing_method = []
        self\
        .register_draw_function(lambda _: True, lambda g, t: draw_text(g, t, str(t.value)))\
        .register_draw_function(lambda t: is_image(t.value), draw_image)\
        .register_draw_function(lambda t: t.function.arity == 0 and "ARG" not in t.function.name, lambda *_: None)

    def clear_set_drawing_methods(self) -> Self:
        """
        Clear the preset drawing methods.

        Returns
        -------
            Itself but with the drawing methods cleared (so it can be used inline).
        """
        self.drawing_method = []
        return self

    def register_draw_function(self, predicate: Callable[[Tree], bool], draw_function: Callable[[pgv.AGraph, Tree], None]) -> Self:
        """
        Register a new draw method.
        The newest draw function will take precidence before the old one, and only one will get called.

        Parameters
        ----------
        predicate : Callable[[Tree], bool]
            The trigger for when to run this draw function, when the predicate returns true, the draw function is called

        draw_function : Callable[[pgv.AGraph, Tree], None]]
            The used to draw the given result

        Returns
        -------
            Itself but with a new drawing methods (so it can be used inline).
        """
        self.drawing_method.insert(0, (predicate, draw_function))
        return self

    def save_graph(self, file: str, tree: Tree, *args: Any) -> None:
        """
        Save the graph visualization of this tree for a given input(s).

        Parameters
        ----------
        file : str
            The filepath to save to.
        tree : Tree
             The tree to convert into a graph.
        *args : Any
            The arguments to pass into the tree to visualize.
        """
        self.get_graph(tree, *args).draw(file)


    def get_graph(self, tree: Tree, *args: Any) -> pgv.AGraph:
        """
        Get the graph visualization of this tree for a given input(s).

        Parameters
        ----------
        tree : Tree
             The tree to convert into a graph.
        *args : Any
            The arguments to pass into the tree to visualize.
        """
        tree._evaluate_all_nodes(*args)

        graph = pgv.AGraph(strict=False, directed=True)

        # requires a directory to store images in :(
        if not os.path.isdir('_treedata'):
            os.makedirs('_treedata')

        self._populate_graph(tree, graph)
        graph.layout(prog="dot")
        return graph

    def _populate_graph(self, tree: Tree, graph: pgv.AGraph) -> None:
        if tree.function.arity == 0:
            graph.add_node(tree.id(), label=tree.function.format())
        else:
            graph.add_node(tree.id(), label=tree.function.name)

        self._display_value(tree, graph)

        for child in tree.children:
            self._populate_graph(child, graph)
            graph.add_edge(tree.id(), child.id(), dir="back")

    def _display_value(self, tree: Tree, graph: pgv.AGraph) -> None:
        for predicate, draw_function in self.drawing_method:
            try:
                if predicate(tree):
                    draw_function(graph, tree)
                    break
            except Exception as e:
                print(e)
        else:
            draw_text(graph, tree, str(tree.value))
        if not graph.has_node(f"{tree.id()}result"):
            return None

        graph.add_edge(tree.id(), f"{tree.id()}result", style="invis", dir="both")

        result_holder = graph.add_subgraph([tree.id(),f"{tree.id()}result"], name=f"{tree.id()}-resultholder")
        result_holder.graph_attr['rank']='same'


def show_img(img: image, title: str='') -> None:
    """
    Display an image to using matplotlib, it renders with a colorbar to show pixel value range
    (as matplotlib automatically scales the image brightness).

    Parameters
    ----------
    img : npt.ArrayLike | PIL.Image.Image
        The image to display, can be anything renderable by pyplot imshow.
    title : str
        The title to give the image, empty by default
    """
    plt.imshow(img, cmap="gray")
    plt.colorbar()
    plt.title(title)
    plt.show()


def save_img(img: image, save_to: str, title: str='') -> None:
    """
    Display an image to using matplotlib, it renders with a colorbar to show pixel value range
    (as matplotlib automatically scales the image brightness).

    Parameters
    ----------
    img : npt.ArrayLike | PIL.Image.Image
        The image to display, can be anything renderable by pyplot imshow.
    save_to : str
        The filepath to save to
    title : str
        The title to give the image, empty by default
    """
    plt.imshow(img, cmap="gray")
    plt.colorbar()
    plt.title(title)
    plt.savefig(save_to, bbox_inches='tight')
    plt.close()


def is_image(value: Any) -> bool:
    """
    Return true if the given value should be rendered as an image (if it is an 2D numpy array or an Image type)

    Parameters
    ----------
    value : Any
        The value to check if it is an image

    Returns
    -------
    bool
        True if it meets this opinionated condition for being rendered as an image.
    """

    return isinstance(value, PIL.Image.Image) or isinstance(value, np.ndarray) and len(value.shape) == 2

def draw_image(graph: pgv.AGraph, tree: Tree[image]) -> None:
    """
    Add an image to the to the given graph with an id of f"{tree.id()}result".

    Parameters
    ----------
    graph : pgv.AGraph
        The graph to add a node to.
    tree : Tree[image]
        The tree to get the image to draw from.
    """
    if tree.value is None:
        raise ValueError("Tried to draw an image for a tree which has not been evaluated.\nMake sure to use `TreeDrawer().get_graph(tree, ...)`, or `tree._evaluate_all_nodes(...)` before running this.")

    save_img(tree.value, save_to=f'_treedata/{tree.id()}.png')

    graph.add_node(f"{tree.id()}result", image=f'_treedata/{tree.id()}.png', label="", imagescale=True, fixedsize=True, shape="plaintext", width=2, height=2)


def draw_text(graph: pgv.AGraph, tree: Tree[Any], text: str) -> None:
    """
    Draw the given text to the graph.

    Parameters
    ----------
    graph : pgv.AGraph
        The graph to add a node to.
    tree : Tree[image]
        This is needed to get the id from
    text : str
        The text to draw to the graph
    """

    graph.add_node(f"{tree.id()}result", label=f"{text}", shape="plaintext")

