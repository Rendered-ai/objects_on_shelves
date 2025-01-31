# Objects on Shelves Channel
Place objects on shelves, modifing objects, placemenet scenes, and lighting using a Blender-based scene with 3D models and rigid body physics. This is a basic Rendered.ai channel for users to learn some of the elements of channel development. Please add or edit nodes, and deploy to your organization to customize your datasets.

## Setup
See the Rendered.ai support documentation for channel development. Get started with [Setting up the Development Environment](https://support.rendered.ai/development-guides/setting-up-the-development-environment):

## Running Locally
To run a graph from this channel, you'll need to locally mount the volumes using the 'anamount' command. This command is part of anatools and requires logging in - make sure to sign up for a free trial account.

The following commands will mount the required volumes then execute the default graph.
```bash
anamount
ana --graph graphs/default.yml --loglevel INFO
```

## Documentation
Documentation has been created for this channel in the docs/ directory. This includes information about graph requirements for the channel, available nodes and other channel-related insights.

## Graphs
The available graphs for the channel are located in the graphs/ directory.

| graph | description |
|---|---|
| default.yml | Places 20 randomized toy objects on a shelf. |

If you run into any problems, please contact admin@rendered.ai for help.