README.rst: README.rst.in docs/intro.rst
	sed -e "/INTRO/ r docs/intro.rst" README.rst.in | sed -e "s/INTRO//" -e "s/:orphan://" >README.rst
