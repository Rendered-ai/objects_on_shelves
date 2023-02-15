import logging
from anatools.lib.node import Node
from anatools.lib.file_handlers import file_to_objgen
from example.nodes.object_generators import ExampleChannelObject

logger = logging.getLogger(__name__)

class Weight(Node):
    """ Modify the weight of a generator/modifier """
    def exec(self):
        logger.info("Executing {}".format(self.name))

        if len(self.inputs["Generator"]) != 1:
            logger.error("Weight 'generator' input port requires exactly 1 link")
            raise ValueError
        # wrap any file objects in an object generator
        generator = file_to_objgen(self.inputs["Generator"], ExampleChannelObject)[0]
        try:
            generator.weight = float(self.inputs["Weight"][0])
        except Exception as e:
            logger.error("{} in \"{}\": \"{}\"".format(type(e).__name__, type(self).__name__, e).replace("\n", ""))
            raise
        return {"Generator": generator}