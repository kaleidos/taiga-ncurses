# -*- coding: utf-8 -*-

"""
gmncurses.controllers.milestone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from concurrent.futures import wait
import functools

from gmncurses.config import ProjectMilestoneKeys
from gmncurses.ui import signals
import gmncurses.data


from . import base


class ProjectMilestoneSubController(base.Controller):
    def __init__(self, view, executor, state_machine):
        self.view = view
        self.executor = executor
        self.state_machine = state_machine

    def handle(self, key):
        if key == ProjectMilestoneKeys.CHANGE_TO_MILESTONE:
            self.change_to_milestone()
        elif key == ProjectMilestoneKeys.RELOAD:
            self.load()
        elif key == ProjectMilestoneKeys.HELP:
            self.help_info()
        else:
            super().handle(key)

    def load(self):
        self.state_machine.transition(self.state_machine.PROJECT_MILESTONES)

        self.view.notifier.info_msg("Fetching Stats and User stories")

        if hasattr(self, "milestone"):
            current_milestone = self.milestone
        else:
            current_milestone = gmncurses.data.current_milestone(self.view.project)

        milestone_f = self.executor.milestone(current_milestone, self.view.project)
        milestone_f.add_done_callback(self.handle_milestone)

        milestone_stats_f = self.executor.milestone_stats(current_milestone, self.view.project)
        milestone_stats_f.add_done_callback(self.handle_milestone_stats)

        user_stories_f = self.executor.user_stories(current_milestone, self.view.project)
        user_stories_f.add_done_callback(self.handle_user_stories)

        tasks_f = self.executor.tasks(current_milestone, self.view.project)
        tasks_f.add_done_callback(self.handle_tasks)

        futures = (tasks_f, user_stories_f)
        futures_completed_f = self.executor.pool.submit(lambda : wait(futures, 10))
        futures_completed_f.add_done_callback(self.handle_user_stories_and_task_info_fetched)

    def change_to_milestone(self):
        self.view.open_milestones_selector_popup(current_milestone=self.milestone)

        signals.connect(self.view.milestone_selector_popup.cancel_button, "click",
                        lambda _: self.cancel_milestone_selector_popup())

        for option in self.view.milestone_selector_popup.options:
            signals.connect(option, "click", functools.partial(self.handler_change_to_milestone))

    def cancel_milestone_selector_popup(self):
        self.view.close_milestone_selector_popup()

    def help_info(self):
        self.view.open_help_popup()

        signals.connect(self.view.help_popup.close_button, "click",
                lambda _: self.close_help_info())

    def close_help_info(self):
        self.view.close_help_popup()

    def handle_milestone(self, future):
        self.milestone = future.result()
        if self.milestone:
            self.view.info.populate(self.milestone)
            self.state_machine.refresh()

    def handle_milestone_stats(self, future):
        self.milestone_stats = future.result()
        if self.milestone_stats:
            self.view.stats.populate(self.milestone_stats)
            self.state_machine.refresh()

    def handle_user_stories(self, future):
        self.user_stories = future.result()

    def handle_tasks(self, future):
        self.tasks = future.result()

    def handle_user_stories_and_task_info_fetched(self, future_with_results):
        done, not_done = future_with_results.result()
        if len(done) == 2:
            self.view.taskboard.populate(self.user_stories, self.tasks)
            self.view.notifier.info_msg("User stories and tasks fetched")
            self.state_machine.refresh()
        else:
            # TODO retry failed operations
            self.view.notifier.error_msg("Failed to fetch milestone data (user stories or task)")

    def handler_change_to_milestone(self, selected_option):
        self.view.notifier.info_msg("Change to milestone '{}'".format(selected_option.milestone["name"]))

        milestone = selected_option.milestone

        milestone_f = self.executor.milestone(milestone, self.view.project)
        milestone_f.add_done_callback(self.handle_milestone)

        milestone_stats_f = self.executor.milestone_stats(milestone, self.view.project)
        milestone_stats_f.add_done_callback(self.handle_milestone_stats)

        user_stories_f = self.executor.user_stories(milestone, self.view.project)
        user_stories_f.add_done_callback(self.handle_user_stories)

        tasks_f = self.executor.tasks(milestone, self.view.project)
        tasks_f.add_done_callback(self.handle_tasks)

        futures = (tasks_f, user_stories_f)
        futures_completed_f = self.executor.pool.submit(lambda : wait(futures, 10))
        futures_completed_f.add_done_callback(self.handle_user_stories_and_task_info_fetched)

        self.cancel_milestone_selector_popup()
