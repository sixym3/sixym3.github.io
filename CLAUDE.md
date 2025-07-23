# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is Eric Xiao's personal portfolio website hosted on GitHub Pages. It's a static HTML website showcasing mechanical engineering and software engineering projects.

## Architecture

- **Static Website**: Built with HTML5, CSS3, and JavaScript
- **Template**: Based on "Stellar" template from HTML5 UP
- **Structure**: Main landing page with separate sections for mechanical and software projects
- **Assets**: SCSS source files compiled to CSS, FontAwesome icons, jQuery libraries

## File Structure

```
/
├── index.html              # Main landing page
├── aboutme.html           # About page
├── mechanical.html        # Mechanical projects overview
├── software.html         # Software projects overview  
├── message.html          # Contact form
├── mechanical/           # Individual mechanical project pages
├── software/            # Individual software project pages
├── assets/
│   ├── css/            # Compiled CSS files
│   ├── sass/           # SCSS source files (organized by components/layout/base)
│   ├── js/             # JavaScript files (jQuery + custom)
│   └── webfonts/       # FontAwesome fonts
├── images/             # Project images organized by category
└── templates/          # Template files (elements.html, generic.html)
```

## Development Commands

This is a static website with no build process. Changes to SCSS files need to be compiled manually to CSS.

For SCSS compilation (if needed):
```bash
# Compile SCSS to CSS (requires Sass)
sass assets/sass/main.scss assets/css/main.css
sass assets/sass/noscript.scss assets/css/noscript.css
```

## Key Components

- **Navigation**: Smooth scrolling navigation implemented in `assets/js/main.js`
- **Responsive Design**: Mobile-first approach using breakpoints defined in `assets/sass/libs/_breakpoints.scss`
- **Image Management**: Project images stored in category-specific folders under `/images/`
- **Template System**: Uses consistent header/footer structure across pages

## Content Management

- Project descriptions are embedded directly in HTML files
- New projects require:
  1. Adding project page in appropriate directory (`mechanical/` or `software/`)
  2. Adding cover image to `/images/mechanical/` or `/images/software/`
  3. Updating overview pages (`mechanical.html` or `software.html`)
  4. Updating main page sections if featured

## Styling Guidelines

- Follows Stellar template conventions
- Custom styles added to maintain consistency
- Uses CSS Grid and Flexbox for layouts
- FontAwesome icons for social media and UI elements