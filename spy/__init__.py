# -*- coding: utf-8 -*-
from django.db import models
from django.db.models.signals import post_init, pre_save, post_save
from django.dispatch.dispatcher import receiver

__author__ = 'nduthoit'


def _watch_name(field_name):
    return "_bug_%s" % field_name

class WatchException(Exception):
    pass

class Agent(object):
    def __init__(self, field_name, on_change, pre_save=True):
        self.field_name = field_name
        self.on_change = on_change
        self.pre_save = pre_save

    def __unicode__(self):
        return u"%s - %s" % (self.field_name, self.on_change)

def spy_on_model(model, agents):
    if not issubclass(model, models.Model):
        raise WatchException("'%s' is not a subclass of django.db.models.Model" % (model.__name__, ))
    model_fields = [field.name for field in model._meta.fields]
    pre_save_agents = []
    post_save_agents = []
    for agent in agents:
        field_name = agent.field_name
        is_pre_save = agent.pre_save
        if not field_name in model_fields:
            raise WatchException("'%s' is not a field of '%s'" % (field_name, model.__name__))
        if is_pre_save:
            pre_save_agents.append(agent)
        else:
            post_save_agents.append(agent)


    # Add an attribute for each agent (a 'bug') to keep track of the field values
    def bug_instance(instance):
        for agent in agents:
            field_name = agent.field_name
            agent_name = _watch_name(field_name)
            current_value = getattr(instance, field_name)
            setattr(instance, agent_name, current_value)

    dispatch_uid = 'spy_post_init_%s' % model.__name__
    @receiver(post_init, sender=model, dispatch_uid=dispatch_uid)
    def init_bugs(sender, instance, **kwargs):
        bug_instance(instance)

    def get_detect_change(pre_save=True):
        if pre_save:
            event_agents = pre_save_agents
        else:
            event_agents = post_save_agents
        def detect_change_and_reset_bugs(sender, instance, **kwargs):
            for agent in event_agents:
                field_name = agent.field_name
                agent_name = _watch_name(field_name)
                old_value = getattr(instance, agent_name)
                new_value = getattr(instance, field_name)
                # If the value has changed, call the on_change method of the agent
                if old_value != new_value:
                    agent.on_change(instance, old_value, new_value)
            # Reset the bugs for this instance
            bug_instance(instance)
        return detect_change_and_reset_bugs

    detect_changes_pre_save = get_detect_change(True)
    detect_changes_post_save = get_detect_change(False)

    if pre_save_agents:
        dispatch_uid = 'spy_pre_save_%s' % model.__name__
        pre_save.connect(detect_changes_pre_save, sender=model, dispatch_uid=dispatch_uid)
    if post_save_agents:
        dispatch_uid = 'spy_post_save_%s' % model.__name__
        post_save.connect(detect_changes_post_save, sender=model, dispatch_uid=dispatch_uid)

    return model

def spy_on(agents):
    def _spy_on_model(model):
        return spy_on_model(model, agents)
    return _spy_on_model

