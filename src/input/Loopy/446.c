// Source: data/benchmarks/sv-benchmarks/loops-crafted-1/mono-crafted_6.c

void loopy_446(void)
{
	int x=0, y=500000, z=0;
	x=0;
	while(x<1000000){
		if(x<500000)
			x++;
		else{
			if(x<750000){
				x++;
			}
			else{
				x=x+2;
			}
			y++;
		}
	}
	 {;
//@ assert(x==1000000);
}

	return;
}