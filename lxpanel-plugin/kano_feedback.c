/*
 * kano_feedback.c
 *
 * Copyright (C) 2014 Kano Computing Ltd.
 * License: http://www.gnu.org/licenses/gpl-2.0.txt GNU General Public License v2
 *
 */

#include <gtk/gtk.h>
#include <gdk/gdk.h>
#include <glib/gi18n.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <gio/gio.h>

#include <lxpanel/plugin.h>

#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <time.h>

#define WIDGET_ICON "/usr/share/kano-feedback/feedback-widget.png"
#define CONTACT_ICON "/usr/share/kano-feedback/media/Icons/Icon-Contact.png"
#define SCREENSHOT_ICON "/usr/share/kano-feedback/media/Icons/Icon-Report.png"
#define KNOWLEDGE_ICON "/usr/share/kano-feedback/media/Icons/Icon-Help.png"

#define PLUGIN_TOOLTIP "Help"
#define CONTACT_CMD "/usr/bin/kano-launcher \"kdesk-blur /usr/bin/kano-feedback\" feedback"
#define REPORT_CMD "kdesk-blur \"/usr/bin/kano-feedback bug\""
#define HELP_CMD "kdesk-blur /usr/bin/kano-help-launcher"

Panel *panel;


static gboolean show_menu(GtkWidget *, GdkEventButton *);
static GtkWidget* get_resized_icon(const char* filename);
static void selection_done(GtkWidget *);
static void popup_set_position(GtkWidget *, gint *, gint *, gboolean *, GtkWidget *);


static int plugin_constructor(Plugin *p, char **fp)
{
    (void)fp;

    panel = p->panel;


    /* need to create a widget to show */
    p->pwid = gtk_event_box_new();

    /* create an icon */
    GtkWidget *icon = gtk_image_new_from_file(WIDGET_ICON);

    /* set border width */
    gtk_container_set_border_width(GTK_CONTAINER(p->pwid), 0);

    /* add the label to the container */
    gtk_container_add(GTK_CONTAINER(p->pwid), GTK_WIDGET(icon));

    /* our widget doesn't have a window... */
    gtk_widget_set_has_window(p->pwid, FALSE);

    gtk_signal_connect(GTK_OBJECT(p->pwid), "button-press-event",
               GTK_SIGNAL_FUNC(show_menu), p);

    /* Set a tooltip to the icon to show when the mouse sits over the it */
    GtkTooltips *tooltips;
    tooltips = gtk_tooltips_new();
    gtk_tooltips_set_tip(tooltips, GTK_WIDGET(icon), PLUGIN_TOOLTIP, NULL);

    gtk_widget_set_sensitive(icon, TRUE);

    /* show our widget */
    gtk_widget_show_all(p->pwid);

    return 1;
}

static void plugin_destructor(Plugin *p)
{
    (void)p;
}

static void launch_cmd(const char *cmd)
{
    GAppInfo *appinfo = NULL;
    gboolean ret = FALSE;

    appinfo = g_app_info_create_from_commandline(cmd, NULL,
                G_APP_INFO_CREATE_NONE, NULL);

    if (appinfo == NULL) {
        perror("Command lanuch failed.");
        return;
    }

    ret = g_app_info_launch(appinfo, NULL, NULL, NULL);
    if (!ret)
        perror("Command lanuch failed.");
}

static void launch_website(const char *url)
{
    const char* cmd;
    // Execute is_internet command
    int internet = system("/usr/bin/is_internet");
    if (internet == 0) {
        char cmd[100];
        strcpy(cmd, "/usr/bin/chromium ");
        strcat(cmd, url);
    }
    else {
        cmd = "sudo kano-settings 4";
    }

    launch_cmd(cmd);
}

void contact_clicked(GtkWidget* widget)
{
    launch_cmd(CONTACT_CMD);
}

void screenshot_clicked(GtkWidget* widget)
{
    launch_cmd(REPORT_CMD);
}

void knowledge_clicked(GtkWidget* widget)
{
    launch_cmd(HELP_CMD);
}

static gboolean show_menu(GtkWidget *widget, GdkEventButton *event)
{
    GtkWidget *menu = gtk_menu_new();
    GtkWidget *header_item;

    if (event->button != 1)
        return FALSE;

    /* Create the menu items */
    header_item = gtk_menu_item_new_with_label("Help");
    gtk_widget_set_sensitive(header_item, FALSE);
    gtk_menu_append(GTK_MENU(menu), header_item);
    gtk_widget_show(header_item);

    /* Contact button */
    GtkWidget* contact_item = gtk_image_menu_item_new_with_label("Contact Us");
    g_signal_connect(contact_item, "activate", G_CALLBACK(contact_clicked), NULL);
    gtk_menu_append(GTK_MENU(menu), contact_item);
    gtk_widget_show(contact_item);
    gtk_image_menu_item_set_image(GTK_IMAGE_MENU_ITEM(contact_item), get_resized_icon(CONTACT_ICON));
    /* Knowledge button */
    GtkWidget* knowledge_item = gtk_image_menu_item_new_with_label("Help Center");
    g_signal_connect(knowledge_item, "activate", G_CALLBACK(knowledge_clicked), NULL);
    gtk_menu_append(GTK_MENU(menu), knowledge_item);
    gtk_widget_show(knowledge_item);
    gtk_image_menu_item_set_image(GTK_IMAGE_MENU_ITEM(knowledge_item), get_resized_icon(KNOWLEDGE_ICON));
    /* Screenshot button */
    GtkWidget* screenshot_item = gtk_image_menu_item_new_with_label("Report a Bug");
    g_signal_connect(screenshot_item, "activate", G_CALLBACK(screenshot_clicked), NULL);
    gtk_menu_append(GTK_MENU(menu), screenshot_item);
    gtk_widget_show(screenshot_item);
    gtk_image_menu_item_set_image(GTK_IMAGE_MENU_ITEM(screenshot_item), get_resized_icon(SCREENSHOT_ICON));

    g_signal_connect(menu, "selection-done", G_CALLBACK(selection_done), NULL);

    /* Show the menu. */
    gtk_menu_popup(GTK_MENU(menu), NULL, NULL,
               (GtkMenuPositionFunc) popup_set_position, widget,
               event->button, event->time);

    return TRUE;
}

static GtkWidget* get_resized_icon(const char* filename)
{
    GError *error = NULL;
    GdkPixbuf* pixbuf = gdk_pixbuf_new_from_file_at_size (filename, 40, 40, &error);
    return gtk_image_new_from_pixbuf(pixbuf);
}

static void selection_done(GtkWidget *menu)
{
    gtk_widget_destroy(menu);
}

/* Helper for position-calculation callback for popup menus. */
void lxpanel_plugin_popup_set_position_helper(Panel * p, GtkWidget * near,
    GtkWidget * popup, GtkRequisition * popup_req, gint * px, gint * py)
{
    /* Get the origin of the requested-near widget in
       screen coordinates. */
    gint x, y;
    gdk_window_get_origin(GDK_WINDOW(near->window), &x, &y);

    /* Doesn't seem to be working according to spec; the allocation.x
       sometimes has the window origin in it */
    if (x != near->allocation.x) x += near->allocation.x;
    if (y != near->allocation.y) y += near->allocation.y;

    /* Dispatch on edge to lay out the popup menu with respect to
       the button. Also set "push-in" to avoid any case where it
       might flow off screen. */
    switch (p->edge)
    {
        case EDGE_TOP:    y += near->allocation.height; break;
        case EDGE_BOTTOM: y -= popup_req->height;       break;
        case EDGE_LEFT:   x += near->allocation.width;  break;
        case EDGE_RIGHT:  x -= popup_req->width;        break;
    }
    *px = x;
    *py = y;
}

/* Position-calculation callback for popup menu. */
static void popup_set_position(GtkWidget *menu, gint *px, gint *py,
                gboolean *push_in, GtkWidget *p)
{
    /* Get the allocation of the popup menu. */
    GtkRequisition popup_req;
    gtk_widget_size_request(menu, &popup_req);

    /* Determine the coordinates. */
    lxpanel_plugin_popup_set_position_helper(panel, p, menu, &popup_req, px, py);
    *push_in = TRUE;
}

static void plugin_configure(Plugin *p, GtkWindow *parent)
{
  // doing nothing here, so make sure neither of the parameters
  // emits a warning at compilation
  (void)p;
  (void)parent;
}

static void plugin_save_configuration(Plugin *p, FILE *fp)
{
  // doing nothing here, so make sure neither of the parameters
  // emits a warning at compilation
  (void)p;
  (void)fp;
}

/* Plugin descriptor. */
PluginClass kano_feedback_plugin_class = {
    // this is a #define taking care of the size/version variables
    PLUGINCLASS_VERSIONING,

    // type of this plugin
    type : "kano_feedback",
    name : N_("Kano Feedback"),
    version: "1.0",
    description : N_("Get help."),

    // we can have many running at the same time
    one_per_system : FALSE,

    // can't expand this plugin
    expand_available : FALSE,

    // assigning our functions to provided pointers.
    constructor : plugin_constructor,
    destructor  : plugin_destructor,
    config : plugin_configure,
    save : plugin_save_configuration
};
