"""
Copyright (c) 2015 Red Hat, Inc
All rights reserved.

This software may be modified and distributed under the terms
of the BSD license. See the LICENSE file for details.
"""

from __future__ import unicode_literals

import json
import os

from atomic_reactor.core import DockerTasker
from atomic_reactor.inner import DockerBuildWorkflow
from atomic_reactor.plugin import PostBuildPluginsRunner, PluginFailedException
from atomic_reactor.util import ImageName
from tests.constants import INPUT_IMAGE, SOURCE
from atomic_reactor.plugins.post_import_image import ImportImagePlugin

import osbs.conf
from osbs.api import OSBS
from osbs.exceptions import OsbsResponseException
from flexmock import flexmock
import pytest


TEST_IMAGESTREAM = "library-imagestream1"
TEST_REPO = "registry.example.com/library/imagestream1"


class X(object):
    image_id = INPUT_IMAGE
    git_dockerfile_path = None
    git_path = None
    base_image = ImageName(repo="qwe", tag="asd")


def prepare():
    """
    Boiler-plate test set-up
    """

    tasker = DockerTasker()
    workflow = DockerBuildWorkflow(SOURCE, "test-image")
    setattr(workflow, 'builder', X())
    setattr(workflow.builder, 'image_id', 'asd123')
    setattr(workflow.builder, 'source', X())
    setattr(workflow.builder.source, 'dockerfile_path', None)
    setattr(workflow.builder.source, 'path', None)
    fake_conf = osbs.conf.Configuration(conf_file=None, openshift_uri='/')
    flexmock(osbs.conf).should_receive('Configuration').and_return(fake_conf)

    runner = PostBuildPluginsRunner(tasker, workflow, [{
        'name': ImportImagePlugin.key,
        'args': {
            'imagestream': TEST_IMAGESTREAM,
            'docker_image_repo': TEST_REPO,
            'url': '',
            'verify_ssl': False,
            'use_auth': False
        }}])

    return runner


def test_bad_setup():
    """
    Try all the early-fail paths.
    """

    runner = prepare()

    (flexmock(OSBS)
     .should_receive('get_image_stream')
     .never())
    (flexmock(OSBS)
     .should_receive('create_image_stream')
     .never())
    (flexmock(OSBS)
     .should_receive('import_image')
     .never())

    # No build JSON
    if "BUILD" in os.environ:
        del os.environ["BUILD"]
    with pytest.raises(PluginFailedException):
        runner.run()


@pytest.mark.parametrize(('namespace'), [
    ({}),
    ({'namespace': 'my_namespace'})
])
def test_create_image(namespace):
    """
    Test that an ImageStream is created if not found
    """

    runner = prepare()

    build_json = {"metadata": {}}
    build_json["metadata"].update(namespace)
    os.environ["BUILD"] = json.dumps(build_json)

    (flexmock(OSBS)
     .should_receive('get_image_stream')
     .once()
     .with_args(TEST_IMAGESTREAM, **namespace)
     .and_raise(OsbsResponseException('none', 404)))
    (flexmock(OSBS)
     .should_receive('create_image_stream')
     .once()
     .with_args(TEST_IMAGESTREAM, TEST_REPO, **namespace))
    (flexmock(OSBS)
     .should_receive('import_image')
     .never())
    runner.run()


@pytest.mark.parametrize(('namespace'), [
    ({}),
    ({'namespace': 'my_namespace'})
])
def test_import_image(namespace):
    """
    Test importing tags for an existing ImageStream
    """

    runner = prepare()

    build_json = {"metadata": {}}
    build_json["metadata"].update(namespace)
    os.environ["BUILD"] = json.dumps(build_json)

    (flexmock(OSBS)
     .should_receive('get_image_stream')
     .once()
     .with_args(TEST_IMAGESTREAM, **namespace))
    (flexmock(OSBS)
     .should_receive('create_image_stream')
     .never())
    (flexmock(OSBS)
     .should_receive('import_image')
     .once()
     .with_args(TEST_IMAGESTREAM, **namespace))
    runner.run()


def test_exception_during_create():
    """
    The plugin should fail if the ImageStream creation fails.
    """

    runner = prepare()
    os.environ["BUILD"] = json.dumps({
        "metadata": {}
    })
    (flexmock(OSBS)
     .should_receive('get_image_stream')
     .with_args(TEST_IMAGESTREAM)
     .and_raise(OsbsResponseException('none', 404)))
    (flexmock(OSBS)
     .should_receive('create_image_stream')
     .once()
     .with_args(TEST_IMAGESTREAM, TEST_REPO)
     .and_raise(RuntimeError))
    (flexmock(OSBS)
     .should_receive('import_image')
     .never())

    with pytest.raises(PluginFailedException):
        runner.run()


def test_exception_during_import():
    """
    The plugin should fail if image import fails.
    """

    runner = prepare()
    os.environ["BUILD"] = json.dumps({
        "metadata": {}
    })
    (flexmock(OSBS)
     .should_receive('get_image_stream')
     .with_args(TEST_IMAGESTREAM)
     .and_raise(OsbsResponseException('none', 404)))
    (flexmock(OSBS)
     .should_receive('create_image_stream')
     .once()
     .with_args(TEST_IMAGESTREAM, TEST_REPO)
     .and_raise(RuntimeError))
    (flexmock(OSBS)
     .should_receive('import_image')
     .never())

    with pytest.raises(PluginFailedException):
        runner.run()
