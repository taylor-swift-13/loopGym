// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/mono-crafted_12.c

void loopy_445(void) {
unsigned int x = 0;
unsigned int y = 10000000;
unsigned int z=0;
	while(x<y){	
		if(x>=5000000)
			z=z+2;
		x++;
	}
  {;
//@ assert(!(z%2));
}

  return;
}